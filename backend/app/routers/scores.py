from fastapi import APIRouter

from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.score import MemberDetailResponse, ScoreResponse
from app.services import projects as project_service

router = APIRouter(tags=["scores"])


@router.get("/projects/{project_id}/scores", response_model=ScoreResponse)
async def get_scores(
    project: MemberProject, user: CurrentUser, db: DB, refresh: bool = False
):
    return await project_service.compute_project_scores(
        db, project, user, force=refresh
    )


@router.get(
    "/projects/{project_id}/members/{login}", response_model=MemberDetailResponse
)
async def get_member_detail(
    login: str, project: MemberProject, user: CurrentUser, db: DB
):
    return await project_service.get_member_detail(db, project, user, login)
