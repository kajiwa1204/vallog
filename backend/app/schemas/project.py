import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CategoryWeights(BaseModel):
    activity: int = Field(ge=0, le=100)
    speed: int = Field(ge=0, le=100)
    quality: int = Field(ge=0, le=100)


class ProjectCreate(BaseModel):
    repo_owner: str
    repo_name: str
    name: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    weights: CategoryWeights | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    repo_owner: str
    repo_name: str
    weights: CategoryWeights
    member_count: int
    github_synced_at: datetime | None
    created_at: datetime


class ProjectListItem(BaseModel):
    id: uuid.UUID
    name: str
    repo_owner: str
    repo_name: str
    member_count: int


class RepoOption(BaseModel):
    owner: str
    name: str
    full_name: str
    private: bool
    description: str | None


class MemberResponse(BaseModel):
    github_login: str
    avatar_url: str | None
    is_registered: bool


class InvitationCreateResponse(BaseModel):
    token: str
    url: str
    expires_at: datetime


class InvitationInfo(BaseModel):
    project_id: uuid.UUID
    project_name: str
    repo_owner: str
    repo_name: str
    member_count: int
    expires_at: datetime


class JoinResponse(BaseModel):
    project_id: uuid.UUID
