from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    encryption_key: str
    jwt_secret: str
    github_client_id: str
    github_client_secret: str
    frontend_url: str
    fastapi_root_path: str = ""
    github_cache_ttl_seconds: int = 300

    # 認証Cookieの Secure 属性。未指定なら FRONTEND_URL のスキームから推定する
    # （localhost では Secure Cookie が送信されないため）。HTTPS 終端が
    # リバースプロキシ側にある構成では明示的に true を指定する。
    cookie_secure: bool | None = None
    # 認証Cookieを送る対象パス。ブラウザから見たパスなので Next の rewrites
    # (`/api/:path*` → backend `/:path*`) を通した後の値を指定する
    auth_cookie_path: str = "/api/auth"

    # LLM provider selection
    summary_provider: Literal["claude", "openai", "ollama"] = "claude"
    # PR diffの1リクエストあたりの最大文字数（Tier1サマリーの入力上限 = コスト上限）
    pr_diff_char_limit: int = 30000

    # Claude
    claude_api_key: str = ""
    claude_pr_model: str = "claude-haiku-4-5-20251001"
    claude_member_model: str = "claude-haiku-4-5-20251001"
    claude_pr_concurrency: int = 5
    claude_member_concurrency: int = 3
    # Haiku非対応。0で無効化。有効時は max_tokens = この値 + 2048 で送信する
    claude_thinking_budget_tokens: int = 1024

    # OpenAI-compatible (Ollama /v1, Gemini free tier, etc.)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_pr_model: str = "gpt-5-nano"
    openai_member_model: str = "gpt-5-nano"
    openai_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "minimal"
    openai_pr_concurrency: int = 5
    openai_member_concurrency: int = 3

    # Ollama native /api/chat
    ollama_base_url: str = "http://localhost:11434"
    ollama_context_length: int = 8192
    ollama_pr_model: str = "qwen3:4b-instruct"
    ollama_member_model: str = "qwen3:4b-instruct"
    ollama_pr_concurrency: int = 2
    ollama_member_concurrency: int = 1

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
