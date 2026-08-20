"""メンバー一覧サービスのGitHub貢献者・登録状態照合テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.services.members import list_members


def _github_client(contributors: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get_contributors = AsyncMock(return_value=contributors)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


async def test_list_members_excludes_all_bot_forms_and_marks_registered_users():
    project = MagicMock(id="project-id", repo_owner="team", repo_name="repo")
    contributors = [
        {"login": "alice", "type": "User", "avatar_url": "https://example.com/a"},
        {"login": "bob", "type": "User", "avatar_url": None},
        {"login": "Copilot", "type": "Bot", "avatar_url": None},
        {"login": "renovate[bot]", "type": "User", "avatar_url": None},
        {"login": "custom-automation", "type": "Bot", "avatar_url": None},
    ]
    repository = MagicMock()
    repository.list_member_users = AsyncMock(
        return_value=[MagicMock(github_login="alice")]
    )

    with (
        patch(
            "app.services.members.GitHubClient",
            return_value=_github_client(contributors),
        ),
        patch("app.services.members.ProjectRepository", return_value=repository),
    ):
        result = await list_members(MagicMock(), project, "token")

    assert [member.github_login for member in result] == ["alice", "bob"]
    assert result[0].is_member is True
    assert result[0].avatar_url == "https://example.com/a"
    assert result[1].is_member is False
    assert result[1].avatar_url == "https://github.com/bob.png"
    repository.list_member_users.assert_awaited_once_with("project-id")
