import uuid

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    github_login: str
    avatar_url: str | None


class TokenResponse(BaseModel):
    access_token: str
    user: UserResponse
