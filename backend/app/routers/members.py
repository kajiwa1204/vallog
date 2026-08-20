from fastapi import APIRouter

from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.project import MemberResponse
from app.services import members as member_service

router = APIRouter(tags=["members"])


@router.get("/projects/{project_id}/members", response_model=list[MemberResponse])
async def list_members(project: MemberProject, user: CurrentUser, db: DB):
    return await member_service.list_members(db, project, user.github_access_token)
