from fastapi import APIRouter

from app.repositories.project import ProjectRepository
from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.project import MemberResponse
from app.services.github import GitHubClient

router = APIRouter(tags=["members"])


@router.get("/projects/{project_id}/members", response_model=list[MemberResponse])
async def list_members(project: MemberProject, user: CurrentUser, db: DB):
    contributors = await GitHubClient(user.github_access_token).get_contributors(
        project.repo_owner, project.repo_name
    )
    registered = {
        u.github_login for u in await ProjectRepository(db).list_member_users(project.id)
    }
    return [
        MemberResponse(
            github_login=c["login"],
            avatar_url=c.get("avatar_url"),
            is_registered=c["login"] in registered,
        )
        for c in contributors
    ]
