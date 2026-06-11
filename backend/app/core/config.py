from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    encryption_key: str
    jwt_secret: str
    github_client_id: str
    github_client_secret: str
    frontend_url: str
    fastapi_root_path: str = ""
    # GitHubキャッシュのTTL（秒）。切れていたらリロード時に再取得する
    github_cache_ttl_seconds: int = 300
    # 貢献サマリー生成用。未設定の場合、サマリー生成APIは503を返す
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-8"

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
