import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Project, User
from app.repositories.project import ProjectRepository

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_project_member(
    project_id: uuid.UUID, user: CurrentUser, db: DB
) -> Project:
    repo = ProjectRepository(db)
    project = await repo.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    if not await repo.is_member(project_id, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このプロジェクトのメンバーではありません",
        )
    return project


MemberProject = Annotated[Project, Depends(require_project_member)]
