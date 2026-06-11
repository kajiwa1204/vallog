from fastapi import APIRouter, status

from app.repositories.project import ProjectRepository
from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.project import (
    InvitationCreateResponse,
    InvitationInfo,
    JoinResponse,
)
from app.services import projects as project_service

router = APIRouter(tags=["invitations"])


@router.post(
    "/projects/{project_id}/invitations",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(project: MemberProject, user: CurrentUser, db: DB):
    return await project_service.create_invitation(db, project, user)


@router.get("/invitations/{token}", response_model=InvitationInfo)
async def get_invitation(token: str, db: DB):
    """招待リンクのプレビュー。ログイン前画面でも表示できるよう認証不要。"""
    invitation = await project_service.get_valid_invitation(db, token)
    project = invitation.project
    count = await ProjectRepository(db).count_members(project.id)
    return InvitationInfo(
        project_id=project.id,
        project_name=project.name,
        repo_owner=project.repo_owner,
        repo_name=project.repo_name,
        member_count=count,
        expires_at=invitation.expires_at,
    )


@router.post("/invitations/{token}/join", response_model=JoinResponse)
async def join(token: str, user: CurrentUser, db: DB):
    project = await project_service.join_via_invitation(db, token, user)
    return JoinResponse(project_id=project.id)
