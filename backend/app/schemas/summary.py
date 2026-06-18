import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    github_login: str
    content: str
    generated_at: datetime


class SummaryJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    github_login: str
    status: str
    total_prs: int
    done_prs: int
    pr_number: int | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class PRSummaryItem(BaseModel):
    """GETのPR一覧レスポンス。生成済みサマリーと最新のPR単独ジョブをマージした形で返す。"""

    pr_number: int
    title: str
    html_url: str
    state: str  # "merged" | "draft" | "open" | "closed"
    content: str | None
    generated_at: datetime | None
    job: SummaryJobResponse | None
