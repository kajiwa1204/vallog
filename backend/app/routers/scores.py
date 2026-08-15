from fastapi import APIRouter

from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.score import ScoreResponse
from app.services import scoring

router = APIRouter(tags=["scores"])


@router.get("/projects/{project_id}/scores", response_model=ScoreResponse)
async def get_scores(project: MemberProject, user: CurrentUser, db: DB):
    """メンバー別のスコアと、その根拠になる生事実。

    開示は「未確定の分配案があるとき」に限る（#100・画面7での事後開示）。判定と拒否は
    条件分岐を伴うので services 側に置く（AGENTS.md「所有チェックによる拒否は
    services を経由する」）。
    """
    return await scoring.get_scores_for_disclosure(
        db, project, user.github_access_token
    )
