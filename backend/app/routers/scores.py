from typing import Annotated

from fastapi import APIRouter, Query

from app.routers.deps import DB, CurrentUser, MemberProject
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

    開示は「未確定の分配案があるとき」に限る（#100・画面7での事後開示）。

    重みを3つとも指定すると、その重みで計算し直したスコアを返す。画面7が**選択中の
    分配案の重み**を渡すために要る。案の配分比率は案の重みで計算されるので、スコアだけ
    プロジェクト既定の重みで返すと、同じ画面の「配分」と「その根拠」が食い違う。

    判定・拒否はどちらも条件分岐なので services 側に置く（AGENTS.md）。
    """
    weights = scoring.resolve_weights(weight_activity, weight_speed, weight_quality)
    return await scoring.get_scores_for_disclosure(
        db, project, user.github_access_token, weights=weights
    )
