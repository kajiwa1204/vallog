from pydantic import BaseModel

from app.schemas.project import CategoryWeights


class CategoryScores(BaseModel):
    """カテゴリごとの相対スコア。各カテゴリはメンバー間で合計1.0（誰も値を持たなければ0.0）。"""

    activity: float
    speed: float
    quality: float


class MemberScore(BaseModel):
    github_login: str
    categories: CategoryScores
    # カテゴリ重みを適用した総合スコア。全メンバーの合計は（全カテゴリに値があれば）1.0
    total: float


class ScoreResponse(BaseModel):
    weights: CategoryWeights
    members: list[MemberScore]
