from pydantic import BaseModel, field_validator


class SetupStatusResponse(BaseModel):
    configured: bool
    callback_url: str


class SetupGitHubRequest(BaseModel):
    client_id: str
    client_secret: str

    @field_validator("client_id", "client_secret")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空文字は指定できません")
        return v.strip()
