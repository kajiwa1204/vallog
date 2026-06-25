import uuid
from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.core.security import get_current_user
from app.models.project import Project
from app.models.user import User
from app.repositories.project import ProjectRepository

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_project_member(
    project_id: uuid.UUID, user: CurrentUser, db: DB
) -> Project:
    repo = ProjectRepository(db)
    project = await repo.get(project_id)
    if project is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND, ErrorCode.PROJECT_NOT_FOUND, "Project not found"
        )
    if not await repo.is_member(project_id, user.id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            ErrorCode.PROJECT_FORBIDDEN,
            "Not a member of this project",
        )
    return project


MemberProject = Annotated[Project, Depends(require_project_member)]
