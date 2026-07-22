from fastapi import APIRouter

from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.score import ScoreResponse
from app.services import scoring

router = APIRouter(tags=["scores"])


@router.get("/projects/{project_id}/scores", response_model=ScoreResponse)
async def get_scores(project: MemberProject, user: CurrentUser, db: DB):
    return await scoring.get_project_scores(db, project, user.github_access_token)
