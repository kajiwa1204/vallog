import secrets
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.models.project import InvitationLink, Project
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.schemas.project import InvitationCreateResponse, ProjectCreate, ProjectUpdate
from app.services.github import GitHubClient

INVITATION_TTL = timedelta(days=7)


async def create_project(db: AsyncSession, user: User, payload: ProjectCreate) -> Project:
    repo = ProjectRepository(db)
    if await repo.get_by_repo(payload.repo_owner, payload.repo_name) is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            ErrorCode.REPO_ALREADY_REGISTERED,
            "Repository is already registered",
        )
    gh_repo = await GitHubClient(user.github_access_token).get_repo(payload.repo_owner, payload.repo_name)
    if gh_repo is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.REPO_NOT_FOUND,
            "Repository not found or access denied",
        )
    project = Project(
        name=payload.name or payload.repo_name,
        repo_owner=payload.repo_owner,
        repo_name=payload.repo_name,
    )
    await repo.create(project)
    await repo.add_member(project.id, user.id)
    await db.commit()
    return project


async def count_members(db: AsyncSession, project_id) -> int:
    return await ProjectRepository(db).count_members(project_id)


async def update_project(db: AsyncSession, project: Project, payload: ProjectUpdate) -> Project:
    if payload.name is not None:
        project.name = payload.name
    if payload.weights is not None:
        w = payload.weights
        project.weight_activity = w.activity
        project.weight_speed = w.speed
        project.weight_quality = w.quality
    await db.commit()
    return project


async def create_invitation(db: AsyncSession, project: Project, user: User) -> InvitationCreateResponse:
    invitation = InvitationLink(
        token=secrets.token_urlsafe(32),
        project_id=project.id,
        created_by=user.id,
        expires_at=datetime.now(timezone.utc) + INVITATION_TTL,
    )
    await ProjectRepository(db).create_invitation(invitation)
    await db.commit()
    return InvitationCreateResponse(
        token=invitation.token,
        url=f"{settings.frontend_url}/invite/{invitation.token}",
        expires_at=invitation.expires_at,
    )


async def get_valid_invitation(db: AsyncSession, token: str) -> InvitationLink:
    invitation = await ProjectRepository(db).get_invitation(token)
    if invitation is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.INVITATION_NOT_FOUND,
            "Invitation link not found",
        )
    if invitation.expires_at < datetime.now(timezone.utc):
        raise AppError(
            status.HTTP_410_GONE,
            ErrorCode.INVITATION_EXPIRED,
            "Invitation link has expired",
        )
    return invitation


async def join_via_invitation(db: AsyncSession, token: str, user: User) -> Project:
    invitation = await get_valid_invitation(db, token)
    project = invitation.project

    # privateリポジトリの場合、アクセス権のないGitHubアカウントの参加を拒否する
    gh_repo = await GitHubClient(user.github_access_token).get_repo(project.repo_owner, project.repo_name)
    if gh_repo is None:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            ErrorCode.REPO_ACCESS_DENIED,
            "Cannot join: no access to this repository",
        )

    await ProjectRepository(db).add_member(project.id, user.id)
    await db.commit()
    return project
