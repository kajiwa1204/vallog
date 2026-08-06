"""services/changelog.py の変化ログ組み立てのユニットテスト。

キャッシュ済みGitHubデータ（ORMオブジェクト）を SimpleNamespace で模して渡す。DBは使わない。
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.changelog import (
    _elapsed_hours,
    _first_external_review,
    build_changelog,
    is_excluded_login,
)


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=timezone.utc)


def _pr(
    number,
    author,
    *,
    created_day=1,
    merged_day=None,
    closed_day=None,
    draft=False,
    reopened=0,
    title=None,
):
    return SimpleNamespace(
        number=number,
        title=title or f"PR {number}",
        author_login=author,
        state="closed" if (merged_day or closed_day) else "open",
        draft=draft,
        html_url=f"https://github.com/o/r/pull/{number}",
        gh_created_at=_dt(created_day),
        merged_at=_dt(merged_day) if merged_day else None,
        closed_at=_dt(closed_day) if closed_day else None,
        reopened_count=reopened,
    )


def _issue(
    number, author, *, sp=None, created_day=1, closed_day=None, assignees=(), title=None
):
    return SimpleNamespace(
        number=number,
        title=title or f"Issue {number}",
        author_login=author,
        state="closed" if closed_day else "open",
        story_points=sp,
        html_url=f"https://github.com/o/r/issues/{number}",
        gh_created_at=_dt(created_day),
        closed_at=_dt(closed_day) if closed_day else None,
        assignees=[SimpleNamespace(login=a, assigned_at=_dt(created_day)) for a in assignees],
    )


def _review(number, reviewer, state="APPROVED", *, day=2, hour=0, submitted=True):
    return SimpleNamespace(
        pr_number=number,
        reviewer_login=reviewer,
        state=state,
        html_url=f"https://github.com/o/r/pull/{number}#review",
        submitted_at=_dt(day, hour) if submitted else None,
    )


# ---------------------------------------------------------------------------
# is_excluded_login
# ---------------------------------------------------------------------------

def test_excludes_bots_and_unknown_fallback():
    assert is_excluded_login("dependabot[bot]")
    assert is_excluded_login("unknown")
    assert not is_excluded_login("alice")


# ---------------------------------------------------------------------------
# _elapsed_hours
# ---------------------------------------------------------------------------

def test_elapsed_hours_rounds_to_one_decimal():
    assert _elapsed_hours(_dt(1, 0), _dt(1, 3)) == 3.0


def test_elapsed_hours_returns_none_when_reversed():
    """レビュー提出がPR作成より前になるような時刻の不整合を、負の数として出さない。"""
    assert _elapsed_hours(_dt(2), _dt(1)) is None


# ---------------------------------------------------------------------------
# _first_external_review
# ---------------------------------------------------------------------------

def test_first_external_review_picks_earliest_by_submitted_at():
    pr = _pr(1, "alice")
    reviews = [_review(1, "bob", day=5), _review(1, "carol", day=3)]
    assert _first_external_review(pr, reviews).reviewer_login == "carol"


def test_first_external_review_ignores_self_review():
    """PR作者が自分のPRに付けたコメントは「レビューされた」に数えない。"""
    pr = _pr(1, "alice")
    assert _first_external_review(pr, [_review(1, "alice", "COMMENTED")]) is None


def test_first_external_review_ignores_pending_review():
    pr = _pr(1, "alice")
    assert _first_external_review(pr, [_review(1, "bob", submitted=False)]) is None


# ---------------------------------------------------------------------------
# build_changelog: エントリの粒度と時刻
# ---------------------------------------------------------------------------

def test_pr_becomes_single_entry_with_merged_state():
    """作成とマージを別行に割らず、PR1件が1エントリになる。"""
    entries = build_changelog([_pr(1, "alice", created_day=1, merged_day=3)], [], []).entries
    assert len(entries) == 1
    assert (entries[0].kind, entries[0].state) == ("pull_request", "merged")
    assert entries[0].occurred_at == _dt(3)


def test_pr_occurred_at_falls_back_to_closed_then_created():
    closed = build_changelog([_pr(1, "alice", created_day=1, closed_day=2)], [], []).entries[0]
    assert (closed.state, closed.occurred_at) == ("closed", _dt(2))

    still_open = build_changelog([_pr(2, "alice", created_day=1)], [], []).entries[0]
    assert (still_open.state, still_open.occurred_at) == ("open", _dt(1))


def test_issue_occurred_at_uses_closed_then_created():
    closed = build_changelog([], [_issue(10, "bob", closed_day=4)], []).entries[0]
    assert (closed.state, closed.occurred_at) == ("closed", _dt(4))

    still_open = build_changelog([], [_issue(11, "bob", created_day=2)], []).entries[0]
    assert (still_open.state, still_open.occurred_at) == ("open", _dt(2))


def test_review_entry_borrows_title_from_its_pull_request():
    prs = [_pr(1, "alice", title="認証の修正")]
    entries = build_changelog(prs, [], [_review(1, "bob", "CHANGES_REQUESTED")]).entries
    review = next(e for e in entries if e.kind == "review")
    assert review.title == "認証の修正"
    assert review.state == "changes_requested"
    assert review.actor_login == "bob"


def test_entries_are_sorted_newest_first_and_limited():
    prs = [_pr(n, "alice", created_day=n, merged_day=n) for n in range(1, 6)]
    entries = build_changelog(prs, [], [], limit=3).entries
    assert [e.number for e in entries] == [5, 4, 3]


# ---------------------------------------------------------------------------
# build_changelog: 事実注記
# ---------------------------------------------------------------------------

def test_pr_notes_record_turnaround_and_external_review():
    prs = [_pr(1, "alice", created_day=1)]
    reviews = [_review(1, "bob", day=1, hour=5)]
    notes = build_changelog(prs, [], reviews).entries[-1].notes
    assert notes.reviewed_by_others is True
    assert notes.turnaround_hours == 5.0


def test_pr_notes_mark_unreviewed_when_only_self_review_exists():
    prs = [_pr(1, "alice", created_day=1)]
    reviews = [_review(1, "alice", "COMMENTED", day=1, hour=5)]
    pr_entry = next(e for e in build_changelog(prs, [], reviews).entries if e.kind == "pull_request")
    assert pr_entry.notes.reviewed_by_others is False
    assert pr_entry.notes.turnaround_hours is None


def test_pr_notes_carry_draft_and_reopened_count():
    notes = build_changelog([_pr(1, "alice", draft=True, reopened=2)], [], []).entries[0].notes
    assert (notes.draft, notes.reopened_count) == (True, 2)


def test_issue_notes_carry_story_points():
    notes = build_changelog([], [_issue(10, "bob", sp=5)], []).entries[0].notes
    assert notes.story_points == 5


# ---------------------------------------------------------------------------
# build_changelog: 除外ルール
# ---------------------------------------------------------------------------

def test_bot_and_unknown_activity_is_dropped():
    prs = [_pr(1, "dependabot[bot]"), _pr(2, "alice")]
    issues = [_issue(10, "unknown")]
    reviews = [_review(2, "dependabot[bot]")]
    entries = build_changelog(prs, issues, reviews).entries
    assert [(e.kind, e.number) for e in entries] == [("pull_request", 2)]


def test_self_review_does_not_become_its_own_entry():
    prs = [_pr(1, "alice")]
    entries = build_changelog(prs, [], [_review(1, "alice", "COMMENTED")]).entries
    assert [e.kind for e in entries] == ["pull_request"]


def test_review_is_dropped_when_its_pull_request_is_not_cached():
    """レビュー対象PRが取得上限から溢れると、タイトルも文脈も出せないため載せない。"""
    entries = build_changelog([], [], [_review(999, "bob")]).entries
    assert entries == []


def test_unsubmitted_review_is_dropped():
    entries = build_changelog([_pr(1, "alice")], [], [_review(1, "bob", submitted=False)]).entries
    assert [e.kind for e in entries] == ["pull_request"]


# ---------------------------------------------------------------------------
# build_changelog: member 絞り込み
# ---------------------------------------------------------------------------

def test_member_filter_keeps_authored_prs_and_reviews_given():
    prs = [_pr(1, "alice"), _pr(2, "bob")]
    reviews = [_review(2, "alice"), _review(1, "bob")]
    entries = build_changelog(prs, [], reviews, member="alice").entries
    assert {(e.kind, e.number) for e in entries} == {("pull_request", 1), ("review", 2)}


def test_member_filter_keeps_issues_authored_or_assigned():
    issues = [
        _issue(10, "alice"),
        _issue(11, "bob", assignees=["alice"]),
        _issue(12, "bob", assignees=["carol"]),
    ]
    entries = build_changelog([], issues, [], member="alice").entries
    assert {e.number for e in entries} == {10, 11}


def test_no_member_filter_returns_whole_team():
    prs = [_pr(1, "alice"), _pr(2, "bob")]
    entries = build_changelog(prs, [], []).entries
    assert {e.number for e in entries} == {1, 2}
