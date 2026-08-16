from typing import Annotated

from fastapi import APIRouter, Query

from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.project import CategoryWeights
from app.schemas.score import ScoreResponse
from app.services import scoring

router = APIRouter(tags=["scores"])

Weight = Annotated[int | None, Query(ge=0, le=100)]


@router.get("/projects/{project_id}/scores", response_model=ScoreResponse)
async def get_scores(
    project: MemberProject,
    user: CurrentUser,
    db: DB,
    weight_activity: Weight = None,
    weight_speed: Weight = None,
    weight_quality: Weight = None,
):
    """メンバー別のスコアと、その根拠になる生事実。

    開示は「未確定の分配案があるとき」に限る（#100・画面7での事後開示）。判定と拒否は
    条件分岐を伴うので services 側に置く（AGENTS.md「所有チェックによる拒否は
    services を経由する」）。

    重みを3つとも指定すると、その重みで計算し直したスコアを返す。画面7が**選択中の
    分配案の重み**を渡すために要る。案の配分比率は案の重みで計算されるので、スコアだけ
    プロジェクト既定の重みで返すと、同じ画面の「配分」と「その根拠」が食い違う。
    一部だけの指定は受け付けない（残りを既定値で埋めると、利用者が指定していない重みが
    黙って混ざる）。
    """
    given = (weight_activity, weight_speed, weight_quality)
    weights = (
        CategoryWeights(
            activity=weight_activity, speed=weight_speed, quality=weight_quality
        )
        if all(w is not None for w in given)
        else None
    )
    return await scoring.get_scores_for_disclosure(
        db, project, user.github_access_token, weights=weights
    )
