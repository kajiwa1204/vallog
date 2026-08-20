from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories.project import ProjectRepository
from app.schemas.project import MemberResponse
from app.services.github import GitHubClient, is_excluded_github_actor


async def list_members(
    db: AsyncSession, project: Project, access_token: str
) -> list[MemberResponse]:
    """GitHub貢献者とVallog登録状況を突き合わせ、人間のメンバー一覧を返す。"""
    async with GitHubClient(access_token) as client:
        contributors = await client.get_contributors(project.repo_owner, project.repo_name)

    registered = {
        user.github_login
        for user in await ProjectRepository(db).list_member_users(project.id)
    }
    return [
        MemberResponse(
            github_login=contributor["login"],
            avatar_url=contributor.get("avatar_url")
            or f"https://github.com/{contributor['login']}.png",
            is_member=contributor["login"] in registered,
        )
        for contributor in contributors
        if not is_excluded_github_actor(
            contributor["login"], contributor.get("type")
        )
    ]
