"""登録フォーム用リポジトリ一覧（services/project.list_selectable_repos）のテスト。

fork の並び順、repo スコープ有無の判定、GET /github/repos のレスポンス形状を
検証する。GitHub API は呼ばない。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.project import RepoOption, RepoOptionList
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


def _github_client(repos: list[dict], scopes: set[str] | None, truncated: bool) -> MagicMock:
    client = MagicMock()
    client.granted_scopes = scopes
    client.list_viewer_repos = AsyncMock(return_value=(repos, truncated))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def _list(
    repos: list[dict],
    scopes: set[str] | None = frozenset({"read:user", "repo"}),
    truncated: bool = False,
):
    user = MagicMock(github_access_token="gho_dummy")
    with patch(
        "app.services.project.GitHubClient",
        return_value=_github_client(repos, None if scopes is None else set(scopes), truncated),
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


async def test_private_access_is_none_when_scopes_unknown():
    """スコープを判定できないときに false を返すと、再認可しても消えない導線が出る。"""
    result = await _list([], scopes=None)

    assert result.private_access is None


async def test_private_repos_are_still_listed_and_flagged():
    result = await _list([_repo("team/secret", private=True)])

    assert result.repos[0].private is True


async def test_truncated_is_passed_through():
    """repo スコープで件数が増えるとページ上限に当たるため、UIで知らせる必要がある。"""
    assert (await _list([], truncated=True)).truncated is True
    assert (await _list([], truncated=False)).truncated is False


# --- GitHubClient.granted_scopes ---


def _response(headers: dict) -> MagicMock:
    res = MagicMock()
    res.status_code = 200
    res.headers = headers
    res.json.return_value = []
    return res


async def test_granted_scopes_parses_header_of_any_response():
    """スコープ専用のリクエストは投げない。ヘッダは全レスポンスに付く。"""
    res = _response({"X-OAuth-Scopes": "read:user, repo"})

    async with GitHubClient("token") as client:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=res) as get:
            await client.list_viewer_repos()

        assert get.call_count == 1
        assert client.granted_scopes == {"read:user", "repo"}


async def test_granted_scopes_is_none_when_header_absent():
    """GitHub App のユーザートークンはこのヘッダを返さない。「スコープ皆無」と混同すると
    移行後に再認可導線が出っぱなしになるため、判定不能として None のままにする。"""
    async with GitHubClient("token") as client:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_response({})):
            await client.list_viewer_repos()

        assert client.granted_scopes is None


async def test_granted_scopes_is_none_before_any_request():
    async with GitHubClient("token") as client:
        assert client.granted_scopes is None


# --- GET /github/repos のレスポンス形状 ---
#
# 配列 → オブジェクトへの breaking change を含むため、形状をここで固定する。


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.core.security import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: MagicMock(
        github_access_token="gho_dummy"
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_github_repos_returns_object_with_repos_and_flags(client):
    payload = RepoOptionList(
        repos=[
            RepoOption(
                owner="team",
                name="upstream",
                full_name="team/upstream",
                private=True,
                fork=False,
                description="desc",
            )
        ],
        private_access=True,
        truncated=False,
    )

    with patch(
        "app.routers.projects.project_service.list_selectable_repos",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        res = client.get("/github/repos")

    assert res.status_code == 200
    assert res.json() == {
        "repos": [
            {
                "owner": "team",
                "name": "upstream",
                "full_name": "team/upstream",
                "private": True,
                "fork": False,
                "description": "desc",
            }
        ],
        "private_access": True,
        "truncated": False,
    }


def test_github_repos_serializes_unknown_private_access_as_null(client):
    payload = RepoOptionList(repos=[], private_access=None, truncated=True)

    with patch(
        "app.routers.projects.project_service.list_selectable_repos",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        res = client.get("/github/repos")

    assert res.status_code == 200
    assert res.json() == {"repos": [], "private_access": None, "truncated": True}
