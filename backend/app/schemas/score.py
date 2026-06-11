from datetime import datetime

from pydantic import BaseModel

from app.schemas.project import CategoryWeights
from app.schemas.summary import SummaryResponse


class MetricRaw(BaseModel):
    """スコアの根拠となる生データ。「なぜそのスコアか」の透明性を担保する。"""

    issues_opened: int
    prs_opened: int
    prs_merged: int
    reviews_commented: int
    approvals: int
    changes_requested: int
    avg_review_tat_hours: float | None
    sp_earned: int
    sp_hours: float
    sp_throughput: float | None
    bugs_assigned: int
    prs_reopened: int


class CategoryScores(BaseModel):
    activity: float
    speed: float
    quality: float


class MemberScore(BaseModel):
    github_login: str
    avatar_url: str | None
    is_registered: bool
    total: float
    categories: CategoryScores
    metrics: MetricRaw


class ScoreResponse(BaseModel):
    synced_at: datetime | None
    weights: CategoryWeights
    members: list[MemberScore]


class TimelinePoint(BaseModel):
    week_start: datetime
    prs: int
    issues: int
    reviews: int


class GitHubItem(BaseModel):
    number: int
    title: str
    state: str
    html_url: str
    created_at: datetime
    extra: str | None = None


class MemberDetailResponse(BaseModel):
    score: MemberScore
    weights: CategoryWeights
    synced_at: datetime | None
    timeline: list[TimelinePoint]
    recent_prs: list[GitHubItem]
    recent_issues: list[GitHubItem]
    recent_reviews: list[GitHubItem]
    summary: SummaryResponse | None
