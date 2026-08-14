from fastapi import APIRouter

from app.repositories.project import ProjectRepository
from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.project import MemberResponse
from app.services.github import GitHubClient

router = APIRouter(tags=["members"])


def _is_bot(contributor: dict) -> bool:
    """人ではない貢献者か。

    login の接尾辞だけでは足りない。GitHub Copilot は login が "Copilot"（"[bot]" が
    付かない）で、type が "Bot" になる。接尾辞だけで弾いていたため一覧に紛れ、
    メンバー詳細（画面5）の切り替え先として「押せるが記録が0件の人」が並んでいた。

    type を先に見て、接尾辞判定は type を返さない応答へのフォールバックとして残す。

    なお変化ログ側の除外（services/changelog.py の is_excluded_login）は
    キャッシュ済みのログイン文字列しか持たないため接尾辞判定のみで、ここと厳密には
    揃わない。botが実際にPR・レビューを出し始めたら、その時点で揃える必要がある。
    """
    return contributor.get("type") == "Bot" or contributor["login"].endswith("[bot]")


@router.get("/projects/{project_id}/members", response_model=list[MemberResponse])
async def list_members(project: MemberProject, user: CurrentUser, db: DB):
    async with GitHubClient(user.github_access_token) as client:
        contributors = await client.get_contributors(project.repo_owner, project.repo_name)
    registered = {
        u.github_login for u in await ProjectRepository(db).list_member_users(project.id)
    }
    return [
        MemberResponse(
            github_login=c["login"],
            avatar_url=c.get("avatar_url") or f"https://github.com/{c['login']}.png",
            is_member=c["login"] in registered,
        )
        for c in contributors
        if not _is_bot(c)
    ]
