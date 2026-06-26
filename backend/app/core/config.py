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

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
