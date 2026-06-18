import uuid

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    github_login: str
    avatar_url: str | None

    model_config = {"from_attributes": True}
