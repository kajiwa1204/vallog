"""LLMプロバイダ抽象化レイヤー。

SUMMARY_PROVIDER=claude|openai|ollama で切り替え。
キャッシュキーにプロバイダ名とモデル名を含めることで、
切替時に古いサマリーが混在するのを防ぐ。
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

_TIMEOUT = 120.0


class SummaryUseCase(str, Enum):
    PR = "pr"
    MEMBER = "member"


@dataclass
class LLMResult:
    content: str
    provider: str
    model: str


def _supports_thinking(model: str) -> bool:
    """Haiku は extended thinking 非対応のため False を返す。"""
    return "haiku" not in model.lower()


class _BaseClient(ABC):
    @abstractmethod
    def _provider_name(self) -> str: ...

    @abstractmethod
    def _model(self, use_case: SummaryUseCase) -> str: ...

    @abstractmethod
    def _semaphore(self, use_case: SummaryUseCase) -> asyncio.Semaphore: ...

    @abstractmethod
    async def _call(self, system: str, user: str, model: str) -> str: ...

    def cache_key_prefix(self, use_case: SummaryUseCase) -> str:
        """キャッシュキーの先頭部分を返す（例: "claude:claude-haiku-4-5-20251001"）。"""
        return f"{self._provider_name()}:{self._model(use_case)}"

    async def complete(self, system: str, user: str, use_case: SummaryUseCase) -> LLMResult:
        model = self._model(use_case)
        async with self._semaphore(use_case):
            content = await self._call(system, user, model)
        if not content.strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="貢献サマリーの生成に失敗しました。",
            )
        return LLMResult(content=content, provider=self._provider_name(), model=model)


class _ClaudeClient(_BaseClient):
    def __init__(self) -> None:
        self._pr_sem = asyncio.Semaphore(settings.claude_pr_concurrency)
        self._member_sem = asyncio.Semaphore(settings.claude_member_concurrency)

    def _provider_name(self) -> str:
        return "claude"

    def _model(self, use_case: SummaryUseCase) -> str:
        return settings.claude_pr_model if use_case == SummaryUseCase.PR else settings.claude_member_model

    def _semaphore(self, use_case: SummaryUseCase) -> asyncio.Semaphore:
        return self._pr_sem if use_case == SummaryUseCase.PR else self._member_sem

    async def _call(self, system: str, user: str, model: str) -> str:
        budget = settings.claude_thinking_budget_tokens
        use_thinking = _supports_thinking(model) and budget > 0
        body: dict = {
            "model": model,
            # thinking 有効時は budget 分のトークンを確保した上で出力領域を 2048 残す
            "max_tokens": (budget + 2048) if use_thinking else 2048,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if use_thinking:
            body["thinking"] = {"type": "enabled", "budget_tokens": budget}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                res = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=body,
                    headers={
                        "x-api-key": settings.claude_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                )
        except httpx.TimeoutException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Claude APIへの接続がタイムアウトしました",
            ) from e
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Claude APIへの接続に失敗しました",
            ) from e

        if res.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Claude APIの認証に失敗しました。CLAUDE_API_KEYを確認してください",
            )
        if res.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Claude APIのレート制限に達しました。しばらくしてから再度お試しください",
            )
        if not res.is_success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Claude APIがエラーを返しました（{res.status_code}）",
            )
        # thinking 有効時はレスポンスに thinking ブロックと text ブロックが混在する
        # content[0] は thinking ブロックになるため type=="text" でフィルタする
        blocks = res.json()["content"]
        return "".join(b["text"] for b in blocks if b.get("type") == "text")


class _OpenAIClient(_BaseClient):
    def __init__(self) -> None:
        self._pr_sem = asyncio.Semaphore(settings.openai_pr_concurrency)
        self._member_sem = asyncio.Semaphore(settings.openai_member_concurrency)

    def _provider_name(self) -> str:
        return "openai"

    def _model(self, use_case: SummaryUseCase) -> str:
        return settings.openai_pr_model if use_case == SummaryUseCase.PR else settings.openai_member_model

    def _semaphore(self, use_case: SummaryUseCase) -> asyncio.Semaphore:
        return self._pr_sem if use_case == SummaryUseCase.PR else self._member_sem

    async def _call(self, system: str, user: str, model: str) -> str:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 2048,
        }
        headers: dict[str, str] = {"content-type": "application/json"}
        # 空のAPIキーで "Authorization: Bearer " を送ると不正ヘッダになるため省略する
        if settings.openai_api_key:
            headers["Authorization"] = f"Bearer {settings.openai_api_key}"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                res = await client.post(
                    f"{settings.openai_base_url}/chat/completions",
                    json=body,
                    headers=headers,
                )
        except httpx.TimeoutException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OpenAI互換APIへの接続がタイムアウトしました",
            ) from e
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OpenAI互換APIへの接続に失敗しました",
            ) from e

        if res.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OpenAI互換APIの認証に失敗しました。OPENAI_API_KEYを確認してください",
            )
        if res.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="OpenAI互換APIのレート制限に達しました。しばらくしてから再度お試しください",
            )
        if not res.is_success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenAI互換APIがエラーを返しました（{res.status_code}）",
            )
        return res.json()["choices"][0]["message"]["content"]


class _OllamaClient(_BaseClient):
    """Ollamaネイティブ /api/chat を使う。

    OpenAI互換エンドポイント（/v1/chat/completions）では qwen3 等の
    thinking が reasoning フィールドに分離されて max_tokens を消費してしまい
    本文が空になる罠があるため、ネイティブAPIで think:false を明示する。
    """

    def __init__(self) -> None:
        self._pr_sem = asyncio.Semaphore(settings.ollama_pr_concurrency)
        self._member_sem = asyncio.Semaphore(settings.ollama_member_concurrency)

    def _provider_name(self) -> str:
        return "ollama"

    def _model(self, use_case: SummaryUseCase) -> str:
        return settings.ollama_pr_model if use_case == SummaryUseCase.PR else settings.ollama_member_model

    def _semaphore(self, use_case: SummaryUseCase) -> asyncio.Semaphore:
        return self._pr_sem if use_case == SummaryUseCase.PR else self._member_sem

    async def _call(self, system: str, user: str, model: str) -> str:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "think": False,
                "num_ctx": settings.ollama_context_length,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                res = await client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json=body,
                )
        except httpx.TimeoutException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Ollamaへの接続がタイムアウトしました",
            ) from e
        except httpx.ConnectError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Ollamaに接続できません。Ollamaが起動しているか確認してください",
            ) from e
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Ollamaへの接続に失敗しました",
            ) from e

        if not res.is_success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ollamaがエラーを返しました（{res.status_code}）",
            )
        return res.json()["message"]["content"]


_client: _BaseClient | None = None


def get_llm_client() -> _BaseClient:
    """設定済みのLLMクライアントを返す。プロセス内でシングルトン。"""
    global _client
    if _client is None:
        match settings.summary_provider:
            case "claude":
                _client = _ClaudeClient()
            case "openai":
                _client = _OpenAIClient()
            case "ollama":
                _client = _OllamaClient()
            case _:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Unknown SUMMARY_PROVIDER: {settings.summary_provider!r}",
                )
    return _client
