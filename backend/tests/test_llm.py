"""services/llm.py のユニットテスト。

HTTP 呼び出しはすべて unittest.mock でスタブし、実際のネットワークは使わない。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import app.services.llm as llm_mod
from app.services.llm import (
    LLMResult,
    SummaryUseCase,
    _ClaudeClient,
    _OllamaClient,
    _OpenAIClient,
    _supports_thinking,
    get_llm_client,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """各テスト前後にシングルトンキャッシュをリセットする。"""
    llm_mod._client = None
    yield
    llm_mod._client = None


def _mock_response(status_code: int, json_body: dict) -> MagicMock:
    res = MagicMock()
    res.status_code = status_code
    res.is_success = 200 <= status_code < 300
    res.json.return_value = json_body
    return res


# ---------------------------------------------------------------------------
# _supports_thinking
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model,expected", [
    ("claude-haiku-4-5-20251001", False),
    ("claude-haiku-3-5",          False),
    ("claude-HAIKU-old",          False),  # 大文字混在
    ("claude-sonnet-4-6",         True),
    ("claude-opus-4-8",           True),
    ("qwen3:4b-instruct",         True),
    ("gemma3:4b",                 True),
])
def test_supports_thinking(model: str, expected: bool):
    assert _supports_thinking(model) == expected


# ---------------------------------------------------------------------------
# cache_key_prefix
# ---------------------------------------------------------------------------

def test_cache_key_prefix_claude(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.summary_provider", "claude")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_member_model", "claude-sonnet-4-6")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_concurrency", 5)
    monkeypatch.setattr("app.services.llm.settings.claude_member_concurrency", 3)

    client = _ClaudeClient()
    assert client.cache_key_prefix(SummaryUseCase.PR) == "claude:claude-haiku-4-5-20251001"
    assert client.cache_key_prefix(SummaryUseCase.MEMBER) == "claude:claude-sonnet-4-6"


def test_cache_key_prefix_openai(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.openai_pr_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm.settings.openai_member_model", "gpt-4o")
    monkeypatch.setattr("app.services.llm.settings.openai_pr_concurrency", 5)
    monkeypatch.setattr("app.services.llm.settings.openai_member_concurrency", 3)

    client = _OpenAIClient()
    assert client.cache_key_prefix(SummaryUseCase.PR) == "openai:gpt-4o-mini"
    assert client.cache_key_prefix(SummaryUseCase.MEMBER) == "openai:gpt-4o"


def test_cache_key_prefix_ollama(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_model", "gemma3:4b")
    monkeypatch.setattr("app.services.llm.settings.ollama_member_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_concurrency", 2)
    monkeypatch.setattr("app.services.llm.settings.ollama_member_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_context_length", 8192)

    client = _OllamaClient()
    assert client.cache_key_prefix(SummaryUseCase.PR) == "ollama:gemma3:4b"
    assert client.cache_key_prefix(SummaryUseCase.MEMBER) == "ollama:qwen3:4b-instruct"


# ---------------------------------------------------------------------------
# get_llm_client ファクトリ
# ---------------------------------------------------------------------------

def test_get_llm_client_returns_claude(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.summary_provider", "claude")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.claude_member_concurrency", 1)
    assert isinstance(get_llm_client(), _ClaudeClient)


def test_get_llm_client_returns_openai(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.summary_provider", "openai")
    monkeypatch.setattr("app.services.llm.settings.openai_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.openai_member_concurrency", 1)
    assert isinstance(get_llm_client(), _OpenAIClient)


def test_get_llm_client_returns_ollama(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.summary_provider", "ollama")
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_member_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_context_length", 8192)
    assert isinstance(get_llm_client(), _OllamaClient)


def test_get_llm_client_singleton(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.summary_provider", "claude")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.claude_member_concurrency", 1)
    assert get_llm_client() is get_llm_client()


def test_get_llm_client_unknown_provider_raises(monkeypatch):
    # pydantic が通常は弾くが、直接代入した場合の case _ を確認
    monkeypatch.setattr("app.services.llm.settings.summary_provider", "unknown")
    with pytest.raises(ValueError, match="Unknown SUMMARY_PROVIDER"):
        get_llm_client()


# ---------------------------------------------------------------------------
# _ClaudeClient のリクエスト / エラー処理
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_claude_complete_success(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.claude_api_key", "sk-test")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_member_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.claude_member_concurrency", 1)

    mock_res = _mock_response(200, {"content": [{"text": "summary text"}]})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        result = await _ClaudeClient().complete("sys", "user", SummaryUseCase.PR)

    assert isinstance(result, LLMResult)
    assert result.content == "summary text"
    assert result.provider == "claude"
    assert result.model == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_claude_401_raises_502(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.claude_api_key", "bad-key")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_member_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.claude_member_concurrency", 1)

    mock_res = _mock_response(401, {"error": "unauthorized"})
    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        with pytest.raises(HTTPException) as exc_info:
            await _ClaudeClient().complete("sys", "user", SummaryUseCase.PR)
    assert exc_info.value.status_code == 502
    assert "CLAUDE_API_KEY" in exc_info.value.detail


@pytest.mark.asyncio
async def test_claude_429_raises_429(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.claude_api_key", "sk-test")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_member_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.claude_member_concurrency", 1)

    mock_res = _mock_response(429, {"error": "rate limited"})
    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        with pytest.raises(HTTPException) as exc_info:
            await _ClaudeClient().complete("sys", "user", SummaryUseCase.PR)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_claude_timeout_raises_502(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.claude_api_key", "sk-test")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_member_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.claude_member_concurrency", 1)

    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(HTTPException) as exc_info:
            await _ClaudeClient().complete("sys", "user", SummaryUseCase.PR)
    assert exc_info.value.status_code == 502
    assert "タイムアウト" in exc_info.value.detail


# ---------------------------------------------------------------------------
# _OpenAIClient — Authorization ヘッダの空キー対策
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_empty_api_key_omits_auth_header(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.openai_api_key", "")
    monkeypatch.setattr("app.services.llm.settings.openai_base_url", "http://localhost:19999/v1")
    monkeypatch.setattr("app.services.llm.settings.openai_pr_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm.settings.openai_member_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm.settings.openai_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.openai_member_concurrency", 1)

    captured_headers: dict = {}

    async def spy(self, url, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        raise httpx.ConnectError("spy")

    with patch("httpx.AsyncClient.post", spy):
        with pytest.raises(Exception):
            await _OpenAIClient()._call("sys", "user", "gpt-4o-mini")

    assert "Authorization" not in captured_headers


@pytest.mark.asyncio
async def test_openai_with_api_key_sends_bearer(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.openai_api_key", "sk-real-key")
    monkeypatch.setattr("app.services.llm.settings.openai_base_url", "http://localhost:19999/v1")
    monkeypatch.setattr("app.services.llm.settings.openai_pr_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm.settings.openai_member_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm.settings.openai_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.openai_member_concurrency", 1)

    captured_headers: dict = {}

    async def spy(self, url, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        raise httpx.ConnectError("spy")

    with patch("httpx.AsyncClient.post", spy):
        with pytest.raises(Exception):
            await _OpenAIClient()._call("sys", "user", "gpt-4o-mini")

    assert captured_headers.get("Authorization") == "Bearer sk-real-key"


# ---------------------------------------------------------------------------
# _OllamaClient — ネイティブエンドポイント / think:false / num_ctx
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ollama_uses_native_endpoint_with_think_false(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.ollama_base_url", "http://ollama:11434")
    monkeypatch.setattr("app.services.llm.settings.ollama_context_length", 16384)
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_member_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_member_concurrency", 1)

    captured: dict = {}

    async def spy(self, url, **kwargs):
        captured["url"] = url
        captured["body"] = kwargs.get("json", {})
        raise httpx.ConnectError("spy")

    with patch("httpx.AsyncClient.post", spy):
        with pytest.raises(Exception):
            await _OllamaClient()._call("sys", "user", "qwen3:4b-instruct")

    assert captured["url"] == "http://ollama:11434/api/chat"
    assert captured["body"]["options"]["think"] is False
    assert captured["body"]["options"]["num_ctx"] == 16384
    assert captured["body"]["stream"] is False


@pytest.mark.asyncio
async def test_ollama_connect_error_raises_502(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr("app.services.llm.settings.ollama_context_length", 8192)
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_member_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_member_concurrency", 1)

    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")):
        with pytest.raises(HTTPException) as exc_info:
            await _OllamaClient().complete("sys", "user", SummaryUseCase.PR)
    assert exc_info.value.status_code == 502
    assert "Ollama" in exc_info.value.detail


@pytest.mark.asyncio
async def test_ollama_complete_success(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.ollama_base_url", "http://ollama:11434")
    monkeypatch.setattr("app.services.llm.settings.ollama_context_length", 8192)
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_member_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_member_concurrency", 1)

    mock_res = _mock_response(200, {"message": {"content": "貢献サマリーです"}})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        result = await _OllamaClient().complete("sys", "user", SummaryUseCase.PR)

    assert result.content == "貢献サマリーです"
    assert result.provider == "ollama"
    assert result.model == "qwen3:4b-instruct"


# ---------------------------------------------------------------------------
# セマフォによる並列度制限
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 非401/429エラーステータスの捕捉（raise_for_status の外出し問題）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("error_status", [500, 503, 404])
@pytest.mark.asyncio
async def test_claude_unexpected_error_raises_502(monkeypatch, error_status):
    monkeypatch.setattr("app.services.llm.settings.claude_api_key", "sk-test")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_member_model", "claude-haiku-4-5-20251001")
    monkeypatch.setattr("app.services.llm.settings.claude_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.claude_member_concurrency", 1)

    mock_res = _mock_response(error_status, {"error": "unexpected"})
    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        with pytest.raises(HTTPException) as exc_info:
            await _ClaudeClient().complete("sys", "user", SummaryUseCase.PR)
    assert exc_info.value.status_code == 502
    assert str(error_status) in exc_info.value.detail


@pytest.mark.parametrize("error_status", [500, 503, 404])
@pytest.mark.asyncio
async def test_openai_unexpected_error_raises_502(monkeypatch, error_status):
    monkeypatch.setattr("app.services.llm.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("app.services.llm.settings.openai_base_url", "http://localhost:19999/v1")
    monkeypatch.setattr("app.services.llm.settings.openai_pr_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm.settings.openai_member_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm.settings.openai_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.openai_member_concurrency", 1)

    mock_res = _mock_response(error_status, {"error": "unexpected"})
    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        with pytest.raises(HTTPException) as exc_info:
            await _OpenAIClient().complete("sys", "user", SummaryUseCase.PR)
    assert exc_info.value.status_code == 502
    assert str(error_status) in exc_info.value.detail


@pytest.mark.parametrize("error_status", [500, 503, 404])
@pytest.mark.asyncio
async def test_ollama_unexpected_error_raises_502(monkeypatch, error_status):
    monkeypatch.setattr("app.services.llm.settings.ollama_base_url", "http://ollama:11434")
    monkeypatch.setattr("app.services.llm.settings.ollama_context_length", 8192)
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_member_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_member_concurrency", 1)

    mock_res = _mock_response(error_status, {"error": "unexpected"})
    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        with pytest.raises(HTTPException) as exc_info:
            await _OllamaClient().complete("sys", "user", SummaryUseCase.PR)
    assert exc_info.value.status_code == 502
    assert str(error_status) in exc_info.value.detail


# ---------------------------------------------------------------------------
# 空・blank レスポンスのガード
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("empty_content", ["", "   ", "\n", "\t\n  "])
@pytest.mark.asyncio
async def test_empty_content_raises_502(monkeypatch, empty_content):
    """空文字・空白のみのレスポンスは 502 を返す（Ollama の thinking 漏れ等の対策）。"""
    monkeypatch.setattr("app.services.llm.settings.ollama_base_url", "http://ollama:11434")
    monkeypatch.setattr("app.services.llm.settings.ollama_context_length", 8192)
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_member_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_member_concurrency", 1)

    mock_res = _mock_response(200, {"message": {"content": empty_content}})
    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
        with pytest.raises(HTTPException) as exc_info:
            await _OllamaClient().complete("sys", "user", SummaryUseCase.PR)
    assert exc_info.value.status_code == 502
    assert "貢献サマリーの生成に失敗しました" in exc_info.value.detail


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(monkeypatch):
    """並列度 1 のセマフォが同時実行を 1 件に制限することを確認する。"""
    monkeypatch.setattr("app.services.llm.settings.ollama_base_url", "http://ollama:11434")
    monkeypatch.setattr("app.services.llm.settings.ollama_context_length", 8192)
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_member_model", "qwen3:4b-instruct")
    monkeypatch.setattr("app.services.llm.settings.ollama_pr_concurrency", 1)
    monkeypatch.setattr("app.services.llm.settings.ollama_member_concurrency", 1)

    concurrent_count = 0
    max_concurrent = 0

    async def slow_post(self, url, **kwargs):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.05)
        concurrent_count -= 1
        return _mock_response(200, {"message": {"content": "ok"}})

    client = _OllamaClient()
    with patch("httpx.AsyncClient.post", slow_post):
        await asyncio.gather(*[
            client.complete("sys", "user", SummaryUseCase.PR) for _ in range(5)
        ])

    assert max_concurrent == 1
