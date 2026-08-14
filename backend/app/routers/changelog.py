from typing import Annotated

from fastapi import APIRouter, Query

from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.changelog import ChangeLogResponse
from app.services import changelog

router = APIRouter(tags=["changelog"])


@router.get("/projects/{project_id}/changelog", response_model=ChangeLogResponse)
async def get_changelog(
    project: MemberProject,
    user: CurrentUser,
    db: DB,
    member: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = changelog.DEFAULT_LIMIT,
):
    return await changelog.get_changelog(
        db, project, user.github_access_token, member=member, limit=limit
    )
