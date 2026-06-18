from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    encryption_key: str
    jwt_secret: str
    # env未設定でもウィザード経由でDB保存できるようデフォルト空文字にする
    github_client_id: str = ""
    github_client_secret: str = ""
    frontend_url: str
    fastapi_root_path: str = ""
    # GitHubキャッシュのTTL（秒）。切れていたらリロード時に再取得する
    github_cache_ttl_seconds: int = 300
    # 貢献サマリー生成用。未設定の場合、サマリー生成APIは503を返す
    anthropic_api_key: str = ""
    claude_pr_summary_model: str = "claude-haiku-4-5"
    claude_member_summary_model: str = "claude-haiku-4-5"

    # LLMプロバイダ選択。"claude" (Anthropic) / "ollama" (ローカル・think無効化のためネイティブAPI使用)
    # / "openai" (OpenAI互換クラウド: Gemini無料枠等)
    summary_provider: str = "claude"
    openai_base_url: str = "http://ollama:11434/v1"
    openai_api_key: str = ""
    # qwen3:4b-instruct は思考モードがなく日本語も堅実で、メモリ8GB級のDocker VMでも動く。16GB+なら qwen3:8b 系や gemma3:12b も選択肢
    openai_pr_summary_model: str = "qwen3:4b-instruct"
    openai_member_summary_model: str = "qwen3:4b-instruct"
    # 0なら自動(claude=4, ollama/openai=1)
    summary_concurrency: int = 0
    # PR diffの1リクエストあたりの最大文字数
    pr_diff_char_limit: int = 30000
    # ローカルLLMのCPU推論は大きなdiffで数分かかるため長めに取る
    llm_request_timeout_seconds: int = 900

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
