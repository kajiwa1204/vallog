"""services/github.py のGitHubキャッシュ取得ロジックのユニットテスト。

HTTP呼び出しはすべて unittest.mock でスタブし、実際のネットワーク・DBは使わない。
"""

import logging
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError, ErrorCode
from app.services.github import (
    GitHubClient,
    _aggregate_issue_events,
    _build_issue_rows,
    _build_pull_request_rows,
    _build_review_rows,
    _count_comments_by_review,
    _parse_dt,
    _parse_dt_required,
    _parse_story_points,
    fetch_and_store,
)


def _mock_response(json_body, status_code: int = 200, headers: dict | None = None) -> MagicMock:
    res = MagicMock()
    res.status_code = status_code
    res.json.return_value = json_body
    res.raise_for_status = MagicMock()
    # _request が X-OAuth-Scopes を読むため、実物同様に添字アクセスできる dict を渡す
    res.headers = headers or {}
    return res


# ---------------------------------------------------------------------------
# _parse_story_points
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("labels,expected", [
    (["SP:3"], 3),
    (["sp:5"], 5),
    (["Sp:8"], 8),
    (["bug", "SP:2", "priority:high"], 2),
    (["bug", "priority:high"], None),
    ([], None),
    (["SP:13"], 13),  # 規定の1/2/3/5/8以外も無条件で受け入れる（意図的な設計判断）
    (["SP:2", "SP:5"], 2),  # 複数のSPラベルが付いた場合は先勝ち
])
def test_parse_story_points(labels, expected):
    assert _parse_story_points(labels) == expected


# ---------------------------------------------------------------------------
# _parse_dt / _parse_dt_required
# ---------------------------------------------------------------------------

def test_parse_dt_returns_none_for_none():
    assert _parse_dt(None) is None


def test_parse_dt_parses_iso_with_z_suffix():
    assert _parse_dt("2026-01-01T00:00:00Z") == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_parse_dt_required_parses_value():
    assert _parse_dt_required("2026-01-01T00:00:00Z") == datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# _aggregate_issue_events
# ---------------------------------------------------------------------------

def test_aggregate_issue_events_assigned_keeps_earliest():
    events = [
        {
            "event": "assigned",
            "issue": {"number": 1},
            "assignee": {"login": "alice"},
            "created_at": "2026-01-02T00:00:00Z",
        },
        {
            "event": "assigned",
            "issue": {"number": 1},
            "assignee": {"login": "alice"},
            "created_at": "2026-01-01T00:00:00Z",
        },
    ]
    assigned_at, reopened = _aggregate_issue_events(events, pr_numbers=set())
    assert assigned_at[(1, "alice")] == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert reopened == {}


def test_aggregate_issue_events_assigned_without_created_at_is_not_recorded():
    events = [{"event": "assigned", "issue": {"number": 1}, "assignee": {"login": "alice"}}]
    assigned_at, _ = _aggregate_issue_events(events, pr_numbers=set())
    assert (1, "alice") not in assigned_at


def test_aggregate_issue_events_ignores_unassigned_event():
    events = [
        {
            "event": "assigned",
            "issue": {"number": 1},
            "assignee": {"login": "alice"},
            "created_at": "2026-01-01T00:00:00Z",
        },
        {"event": "unassigned", "issue": {"number": 1}, "assignee": {"login": "alice"}},
    ]
    assigned_at, reopened = _aggregate_issue_events(events, pr_numbers=set())
    assert assigned_at[(1, "alice")] == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert reopened == {}


def test_aggregate_issue_events_counts_reopened_only_for_pr_numbers():
    events = [
        {"event": "reopened", "issue": {"number": 5}},  # PR
        {"event": "reopened", "issue": {"number": 5}},  # PR
        {"event": "reopened", "issue": {"number": 6}},  # 素のissue。PR再オープン回数には含めない
        {"event": "closed", "issue": {"number": 6}},
    ]
    assigned_at, reopened = _aggregate_issue_events(events, pr_numbers={5})
    assert assigned_at == {}
    assert reopened == {5: 2}


def test_aggregate_issue_events_ignores_events_without_issue_number():
    events = [{"event": "assigned", "assignee": {"login": "alice"}}]
    assigned_at, reopened = _aggregate_issue_events(events, pr_numbers=set())
    assert assigned_at == {}
    assert reopened == {}


# ---------------------------------------------------------------------------
# _count_comments_by_review
# ---------------------------------------------------------------------------

def test_count_comments_by_review():
    comments = [
        {"pull_request_review_id": 100},
        {"pull_request_review_id": 100},
        {"pull_request_review_id": 200},
        {"pull_request_review_id": None},
    ]
    assert _count_comments_by_review(comments) == {100: 2, 200: 1}


# ---------------------------------------------------------------------------
# _build_pull_request_rows / _build_issue_rows / _build_review_rows
# ---------------------------------------------------------------------------

def test_build_pull_request_rows_applies_reopened_count():
    pulls = [
        {
            "id": 1,
            "number": 42,
            "title": "Add feature",
            "user": {"login": "bob"},
            "state": "closed",
            "draft": False,
            "html_url": "https://example.com/42",
            "created_at": "2026-01-01T00:00:00Z",
            "merged_at": "2026-01-02T00:00:00Z",
            "closed_at": "2026-01-02T00:00:00Z",
        }
    ]
    rows = _build_pull_request_rows(pulls, {42: 3})
    assert len(rows) == 1
    assert rows[0].reopened_count == 3
    assert rows[0].author_login == "bob"
    assert rows[0].merged_at == datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_build_pull_request_rows_falls_back_to_unknown_for_deleted_account(caplog):
    pulls = [
        {
            "id": 1,
            "number": 1,
            "title": "t",
            "user": None,  # GitHubアカウント削除済みの場合に返る形
            "state": "open",
            "draft": False,
            "html_url": "https://example.com/1",
            "created_at": "2026-01-01T00:00:00Z",
            "merged_at": None,
            "closed_at": None,
        }
    ]
    with caplog.at_level(logging.WARNING):
        rows = _build_pull_request_rows(pulls, {})
    assert rows[0].author_login == "unknown"
    assert "actor login missing" in caplog.text


def test_build_issue_rows_excludes_pull_requests():
    issues = [
        {
            "id": 1,
            "number": 1,
            "title": "PR disguised as issue",
            "user": {"login": "carol"},
            "state": "open",
            "labels": [],
            "html_url": "https://example.com/1",
            "created_at": "2026-01-01T00:00:00Z",
            "pull_request": {"url": "https://example.com/pulls/1"},
        },
        {
            "id": 2,
            "number": 2,
            "title": "Real issue",
            "user": {"login": "carol"},
            "state": "open",
            "labels": [{"name": "SP:5"}],
            "html_url": "https://example.com/2",
            "created_at": "2026-01-01T00:00:00Z",
            "assignees": [{"login": "carol"}],
        },
    ]
    rows = _build_issue_rows(issues, {(2, "carol"): datetime(2026, 1, 1, tzinfo=timezone.utc)})
    assert len(rows) == 1
    assert rows[0].number == 2
    assert rows[0].story_points == 5
    assert rows[0].assignees[0].login == "carol"
    assert rows[0].assignees[0].assigned_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_build_review_rows_applies_comment_count():
    reviews_by_pr = {
        42: [
            {
                "id": 100,
                "user": {"login": "dave"},
                "state": "APPROVED",
                "body": "",
                "html_url": "https://example.com/reviews/100",
                "submitted_at": "2026-01-03T00:00:00Z",
            }
        ]
    }
    rows = _build_review_rows(reviews_by_pr, {100: 4})
    assert len(rows) == 1
    assert rows[0].pr_number == 42
    assert rows[0].comment_count == 4
    assert rows[0].reviewer_login == "dave"
    assert rows[0].state == "APPROVED"
    assert rows[0].submitted_at == datetime(2026, 1, 3, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# GitHubClient._paginated / list_viewer_repos / _request
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paginated_stops_when_batch_smaller_than_per_page():
    client = GitHubClient("token")
    page1 = _mock_response([{"id": i} for i in range(2)])
    page2 = _mock_response([{"id": 99}])

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[page1, page2]) as mock_get:
        results = await client._paginated("/some/path", {}, max_pages=5, per_page=2)

    assert len(results) == 3
    assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_paginated_respects_max_pages():
    client = GitHubClient("token")
    full_page = _mock_response([{"id": i} for i in range(2)])

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=full_page) as mock_get:
        results = await client._paginated("/some/path", {}, max_pages=3, per_page=2)

    assert len(results) == 6
    assert mock_get.call_count == 3


@pytest.mark.asyncio
async def test_list_viewer_repos_uses_paginated():
    client = GitHubClient("token")
    page = _mock_response([{"id": 1, "full_name": "owner/repo"}])

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=page):
        repos, truncated = await client.list_viewer_repos()

    assert repos == [{"id": 1, "full_name": "owner/repo"}]
    assert truncated is False


@pytest.mark.asyncio
async def test_request_raises_app_error_for_rate_limit():
    client = GitHubClient("token")
    res = _mock_response({}, status_code=429)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=res):
        with pytest.raises(AppError) as exc_info:
            await client._request("/some/path")

    assert exc_info.value.code == ErrorCode.GITHUB_RATE_LIMITED


@pytest.mark.asyncio
async def test_request_raises_app_error_for_server_error():
    client = GitHubClient("token")
    res = _mock_response({}, status_code=503)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=res):
        with pytest.raises(AppError) as exc_info:
            await client._request("/some/path")

    assert exc_info.value.code == ErrorCode.GITHUB_UNAVAILABLE


@pytest.mark.asyncio
async def test_list_reviews_for_prs_maps_by_number():
    client = GitHubClient("token")

    async def fake_request(path, params=None):
        if path.endswith("/10/reviews"):
            return _mock_response([{"id": 1}])
        if path.endswith("/20/reviews"):
            return _mock_response([{"id": 2}, {"id": 3}])
        raise AssertionError(f"unexpected path {path}")

    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=fake_request):
        result = await client.list_reviews_for_prs("o", "r", [10, 20])

    assert result == {10: [{"id": 1}], 20: [{"id": 2}, {"id": 3}]}


# ---------------------------------------------------------------------------
# fetch_and_store
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_and_store_wires_fetched_data_into_repository():
    client = AsyncMock()
    client.list_pull_requests.return_value = [
        {
            "id": 1,
            "number": 42,
            "title": "t",
            "user": {"login": "alice"},
            "state": "open",
            "draft": False,
            "html_url": "https://example.com/42",
            "created_at": "2026-01-01T00:00:00Z",
            "merged_at": None,
            "closed_at": None,
        }
    ]
    client.list_issues.return_value = []
    client.list_issue_events.return_value = []
    client.list_review_comments.return_value = []
    client.list_reviews_for_prs.return_value = {}

    project = MagicMock()
    project.id = uuid.uuid4()
    project.repo_owner = "owner"
    project.repo_name = "repo"

    db = MagicMock()

    with patch("app.services.github.GitHubCacheRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.upsert_pull_requests = AsyncMock()
        mock_repo.upsert_issues = AsyncMock()
        mock_repo.upsert_reviews = AsyncMock()

        await fetch_and_store(client, project, db)

    client.list_reviews_for_prs.assert_awaited_once_with("owner", "repo", [42])

    mock_repo.upsert_pull_requests.assert_awaited_once()
    pr_call_project_id, pr_rows = mock_repo.upsert_pull_requests.await_args.args
    assert pr_call_project_id == project.id
    assert len(pr_rows) == 1
    assert pr_rows[0].number == 42

    mock_repo.upsert_issues.assert_awaited_once_with(project.id, [])
    mock_repo.upsert_reviews.assert_awaited_once_with(project.id, [])
