import re
from typing import Literal

import anthropic
import httpx
from fastapi import HTTPException, status

from app.core.config import settings

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _resolve_concurrency(tier: Literal["pr", "member"]) -> int:
    if settings.summary_concurrency > 0:
        return settings.summary_concurrency
    if settings.summary_provider in ("openai", "ollama"):
        return 1
    return 4


async def _chat_claude(system: str, user: str, tier: Literal["pr", "member"], max_tokens: int) -> str:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claude APIキーが未設定のため、貢献サマリーを生成できません。",
        )
    model = (
        settings.claude_pr_summary_model if tier == "pr"
        else settings.claude_member_summary_model
    )
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


async def _chat_openai(system: str, user: str, tier: Literal["pr", "member"], max_tokens: int) -> str:
    model = (
        settings.openai_pr_summary_model if tier == "pr"
        else settings.openai_member_summary_model
    )
    # Qwen3は思考モードが既定ONで、max_tokensを思考に使い切り本文が空になりうる。
    # ソフトスイッチ /no_think で思考を無効化する
    if "qwen3" in model.lower():
        user = f"{user}\n/no_think"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    # キー不要のOllama等では空になる。空のBearerは不正ヘッダ扱いされるため付けない
    headers = (
        {"Authorization": f"Bearer {settings.openai_api_key}"}
        if settings.openai_api_key
        else {}
    )
    base_url = settings.openai_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.llm_request_timeout_seconds)
        ) as client:
            res = await client.post(
                f"{base_url}/chat/completions",
                json=body,
                headers=headers,
            )
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"ローカルLLM/外部APIに接続できません: {base_url}。"
                "Ollamaの場合は `docker compose --profile ollama up -d` で起動してください。"
            ),
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ローカルLLM/外部APIへのリクエストに失敗しました: {e}",
        ) from e

    if res.status_code != 200:
        # 「model not found(未pull)」等の原因がユーザーに見えるよう、レスポンス本文を含める
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"ローカルLLM/外部APIがエラーを返しました: HTTP {res.status_code} "
                f"{res.text[:300]}"
            ),
        )

    content = res.json()["choices"][0]["message"]["content"].strip()
    # Qwen3等の思考モード対策: <think>...</think> ブロックを除去する
    return _THINK_BLOCK_RE.sub("", content).strip()


async def _chat_ollama(system: str, user: str, tier: Literal["pr", "member"], max_tokens: int) -> str:
    """OllamaネイティブAPI(/api/chat)を使う。

    OpenAI互換エンドポイントでは思考(reasoning)を無効化できず、
    qwen3等の思考モデルが max_tokens を思考で使い切り本文が空になるため、
    think:false を正式サポートするネイティブAPIを使う。
    """
    model = (
        settings.openai_pr_summary_model if tier == "pr"
        else settings.openai_member_summary_model
    )
    root = settings.openai_base_url.rstrip("/").removesuffix("/v1")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,
        "options": {"num_predict": max_tokens},
    }
    timeout = httpx.Timeout(settings.llm_request_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(f"{root}/api/chat", json=body)
            # gemma3等の思考非対応モデルは think 指定を400で拒否するため、外して再試行
            if res.status_code == 400 and "think" in res.text:
                body.pop("think", None)
                res = await client.post(f"{root}/api/chat", json=body)
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"Ollamaに接続できません: {root}。"
                "`docker compose --profile ollama up -d` で起動してください。"
            ),
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"Ollamaの応答が{settings.llm_request_timeout_seconds}秒以内に返りませんでした。"
                "CPU推論では時間がかかるため、LLM_REQUEST_TIMEOUT_SECONDS の引き上げ、"
                "より小さいモデル、PR_DIFF_CHAR_LIMIT の縮小を検討してください。"
            ),
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollamaへのリクエストに失敗しました: {type(e).__name__}: {e}",
        ) from e

    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollamaがエラーを返しました: HTTP {res.status_code} {res.text[:300]}",
        )

    content = res.json()["message"]["content"].strip()
    return _THINK_BLOCK_RE.sub("", content).strip()


async def chat(
    system: str,
    user: str,
    tier: Literal["pr", "member"],
    max_tokens: int,
) -> str:
    """LLMにチャット補完を要求し、テキストを返す。

    プロバイダは settings.summary_provider で切り替える。
    """
    if settings.summary_provider == "claude":
        return await _chat_claude(system, user, tier, max_tokens)
    if settings.summary_provider == "ollama":
        return await _chat_ollama(system, user, tier, max_tokens)
    if settings.summary_provider == "openai":
        return await _chat_openai(system, user, tier, max_tokens)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"不正なsummary_providerです: {settings.summary_provider}",
    )
