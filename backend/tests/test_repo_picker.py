"""登録フォーム用リポジトリ一覧（services/project.list_selectable_repos）のテスト。

fork の並び順と、repo スコープ有無の判定を検証する。GitHub API は呼ばない。
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.services.github import GitHubClient
from app.services.project import list_selectable_repos


def _repo(full_name: str, *, private: bool = False, fork: bool = False, **extra) -> dict:
    owner, name = full_name.split("/")
    return {
        "owner": {"login": owner},
        "name": name,
        "full_name": full_name,
        "private": private,
        "fork": fork,
        "description": None,
        **extra,
    }


def _github_client(repos: list[dict], scopes: set[str]) -> MagicMock:
    client = MagicMock()
    client.get_granted_scopes = AsyncMock(return_value=scopes)
    client.list_viewer_repos = AsyncMock(return_value=repos)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def _list(repos: list[dict], scopes: set[str] = frozenset({"read:user", "repo"})):
    user = MagicMock(github_access_token="gho_dummy")
    with patch(
        "app.services.project.GitHubClient",
        return_value=_github_client(repos, set(scopes)),
    ):
        return await list_selectable_repos(user)


async def test_forks_are_listed_after_non_forks():
    """上流と自分のforkが並ぶと選び間違えるため、forkは後ろへ回す。"""
    result = await _list([
        _repo("me/my-fork", fork=True),
        _repo("team/upstream"),
        _repo("me/another-fork", fork=True),
        _repo("team/other"),
    ])

    assert [r.full_name for r in result.repos] == [
        "team/upstream",
        "team/other",
        "me/my-fork",
        "me/another-fork",
    ]


async def test_pushed_order_is_preserved_within_each_group():
    """GitHub の sort=pushed 順を group 内で崩さない（sort が安定であること）。"""
    result = await _list([
        _repo("team/a"),
        _repo("me/f1", fork=True),
        _repo("team/b"),
        _repo("me/f2", fork=True),
        _repo("team/c"),
    ])

    assert [r.full_name for r in result.repos] == [
        "team/a", "team/b", "team/c", "me/f1", "me/f2",
    ]


async def test_fork_flag_is_exposed():
    result = await _list([_repo("team/upstream"), _repo("me/my-fork", fork=True)])

    assert {r.full_name: r.fork for r in result.repos} == {
        "team/upstream": False,
        "me/my-fork": True,
    }


async def test_missing_fork_key_defaults_to_false():
    repo = _repo("team/upstream")
    del repo["fork"]

    result = await _list([repo])

    assert result.repos[0].fork is False


async def test_private_access_true_when_repo_scope_granted():
    result = await _list([], scopes={"read:user", "repo"})

    assert result.private_access is True


async def test_private_access_false_without_repo_scope():
    """repo スコープがないとGitHubは公開リポジトリしか返さないため、再認可が必要。"""
    result = await _list([], scopes={"read:user"})

    assert result.private_access is False


async def test_private_repos_are_still_listed_and_flagged():
    result = await _list([_repo("team/secret", private=True)])

    assert result.repos[0].private is True


# --- GitHubClient.get_granted_scopes ---


def _response(headers: dict) -> MagicMock:
    res = MagicMock()
    res.status_code = 200
    res.headers = headers
    res.json.return_value = {}
    return res


async def test_get_granted_scopes_parses_header():
    client = GitHubClient("token")
    res = _response({"X-OAuth-Scopes": "read:user, repo"})

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=res):
        scopes = await client.get_granted_scopes()

    assert scopes == {"read:user", "repo"}


async def test_get_granted_scopes_is_empty_when_header_absent():
    client = GitHubClient("token")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_response({})):
        scopes = await client.get_granted_scopes()

    assert scopes == set()
