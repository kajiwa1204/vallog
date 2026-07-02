"""services/github.py のGitHubキャッシュ取得ロジックのユニットテスト。

HTTP呼び出しはすべて unittest.mock でスタブし、実際のネットワーク・DBは使わない。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.github import (
    GitHubClient,
    _aggregate_issue_events,
    _build_issue_rows,
    _build_pull_request_rows,
    _build_review_rows,
    _count_comments_by_review,
    _parse_story_points,
)


def _mock_response(json_body, status_code: int = 200) -> MagicMock:
    res = MagicMock()
    res.status_code = status_code
    res.json.return_value = json_body
    res.raise_for_status = MagicMock()
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
])
def test_parse_story_points(labels, expected):
    assert _parse_story_points(labels) == expected


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
    assigned_at, reopened = _aggregate_issue_events(events)
    assert assigned_at[(1, "alice")] == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert reopened == {}


def test_aggregate_issue_events_counts_reopened():
    events = [
        {"event": "reopened", "issue": {"number": 5}},
        {"event": "reopened", "issue": {"number": 5}},
        {"event": "reopened", "issue": {"number": 6}},
        {"event": "closed", "issue": {"number": 6}},
    ]
    assigned_at, reopened = _aggregate_issue_events(events)
    assert assigned_at == {}
    assert reopened == {5: 2, 6: 1}


def test_aggregate_issue_events_ignores_events_without_issue_number():
    events = [{"event": "assigned", "assignee": {"login": "alice"}}]
    assigned_at, reopened = _aggregate_issue_events(events)
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


# ---------------------------------------------------------------------------
# GitHubClient._paginated / list_viewer_repos
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
        repos = await client.list_viewer_repos()

    assert repos == [{"id": 1, "full_name": "owner/repo"}]
