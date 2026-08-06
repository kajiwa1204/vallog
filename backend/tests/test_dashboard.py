"""services/dashboard.py のチーム状況パネル4種のユニットテスト。

キャッシュ済みGitHubデータ（ORMオブジェクト）を SimpleNamespace で模して渡す。DBは使わない。
現在時刻は build_dashboard の引数で渡すため、実行時の時計に依存しない。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.dashboard import (
    DEFAULT_PULSE_DAYS,
    STALLED_ISSUE_DAYS,
    _local_date,
    build_dashboard,
)

NOW = datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc)


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=timezone.utc)


def _pr(
    number,
    author,
    *,
    created_day=1,
    created_hour=0,
    merged_day=None,
    closed_day=None,
    draft=False,
    reopened=0,
):
    return SimpleNamespace(
        number=number,
        title=f"PR {number}",
        author_login=author,
        state="closed" if (merged_day or closed_day) else "open",
        draft=draft,
        html_url=f"https://github.com/o/r/pull/{number}",
        gh_created_at=_dt(created_day, created_hour),
        merged_at=_dt(merged_day) if merged_day else None,
        closed_at=_dt(closed_day) if closed_day else None,
        reopened_count=reopened,
    )


def _issue(
    number,
    author,
    *,
    labels=(),
    sp=None,
    created_day=1,
    closed_day=None,
    state_reason=None,
    assignees=(),
):
    return SimpleNamespace(
        number=number,
        title=f"Issue {number}",
        author_login=author,
        state="closed" if closed_day else "open",
        state_reason=state_reason,
        labels=list(labels),
        story_points=sp,
        html_url=f"https://github.com/o/r/issues/{number}",
        gh_created_at=_dt(created_day),
        closed_at=_dt(closed_day) if closed_day else None,
        assignees=list(assignees),
    )


def _assignee(login, assigned_day=None):
    return SimpleNamespace(
        login=login,
        assigned_at=_dt(assigned_day) if assigned_day else None,
    )


def _review(number, reviewer, state="APPROVED", *, day=2, hour=0, github_id=None):
    review_id = github_id if github_id is not None else number * 1000
    return SimpleNamespace(
        github_id=review_id,
        pr_number=number,
        reviewer_login=reviewer,
        state=state,
        html_url=f"https://github.com/o/r/pull/{number}#pullrequestreview-{review_id}",
        submitted_at=_dt(day, hour),
    )


def _build(prs=(), issues=(), reviews=(), **kwargs):
    kwargs.setdefault("now", NOW)
    return build_dashboard(list(prs), list(issues), list(reviews), **kwargs)


# --- pulse ---------------------------------------------------------------


def test_pulse_fills_quiet_days_with_zero():
    result = _build(prs=[_pr(1, "alice", created_day=20)])

    assert len(result.pulse) == DEFAULT_PULSE_DAYS
    # 古い→新しい順で、末尾が「今日」
    assert result.pulse[-1].date == NOW.date()
    assert result.pulse[-1].pull_requests == 1
    assert all(d.pull_requests == 0 for d in result.pulse[:-1])


def test_pulse_counts_each_kind_separately():
    result = _build(
        prs=[_pr(1, "alice", created_day=20)],
        issues=[_issue(2, "bob", created_day=20)],
        reviews=[_review(1, "bob", day=20)],
    )

    today = result.pulse[-1]
    assert (today.pull_requests, today.issues, today.reviews) == (1, 1, 1)


def test_pulse_uses_latest_state_change_not_creation():
    """変化ログと同じ時刻を採る。作成日で数えるとバーと一覧の日付がズレる。"""
    # 作成・マージともに14日窓（1/7〜1/20）の内側に置き、どちらの日で数えたかを見る
    result = _build(prs=[_pr(1, "alice", created_day=8, merged_day=20)])

    by_date = {d.date: d for d in result.pulse}
    assert by_date[_dt(20).date()].pull_requests == 1
    assert by_date[_dt(8).date()].pull_requests == 0


def test_pulse_drops_activity_outside_the_window():
    result = _build(prs=[_pr(1, "alice", created_day=1)], days=5)

    assert len(result.pulse) == 5
    assert sum(d.pull_requests for d in result.pulse) == 0


def test_pulse_buckets_by_local_date_when_offset_given():
    """23:00 UTC は JST では翌日。オフセットを渡すと翌日のバーに入る。"""
    late_utc = [_pr(1, "alice", created_day=19, created_hour=23)]

    utc = _build(prs=late_utc)
    jst = _build(prs=late_utc, tz_offset_minutes=540)

    assert next(d for d in utc.pulse if d.date == _dt(19).date()).pull_requests == 1
    assert next(d for d in jst.pulse if d.date == _dt(20).date()).pull_requests == 1


def test_local_date_shifts_across_midnight():
    assert _local_date(_dt(19, 23), 540) == _dt(20).date()
    assert _local_date(_dt(19, 23), 0) == _dt(19).date()


def test_pulse_excludes_bots():
    result = _build(prs=[_pr(1, "dependabot[bot]", created_day=20)])

    assert sum(d.pull_requests for d in result.pulse) == 0


# --- attention -----------------------------------------------------------


def test_review_wanted_lists_open_prs_without_external_review():
    result = _build(prs=[_pr(1, "alice", created_day=18)])

    assert [p.number for p in result.attention.review_wanted] == [1]
    assert result.attention.review_wanted[0].waiting_hours == 60.0


def test_review_wanted_excludes_prs_already_reviewed_by_others():
    result = _build(
        prs=[_pr(1, "alice", created_day=18)],
        reviews=[_review(1, "bob", day=19)],
    )

    assert result.attention.review_wanted == []


def test_self_review_does_not_clear_review_wanted():
    """作者本人のコメントで「レビュー済み」にすると、放置PRがパネルから消える。"""
    result = _build(
        prs=[_pr(1, "alice", created_day=18)],
        reviews=[_review(1, "alice", state="COMMENTED", day=19)],
    )

    assert [p.number for p in result.attention.review_wanted] == [1]


def test_drafts_are_separated_from_review_wanted():
    result = _build(prs=[_pr(1, "alice", created_day=18, draft=True)])

    assert result.attention.review_wanted == []
    assert [p.number for p in result.attention.drafts] == [1]
    assert result.attention.drafts[0].draft is True


def test_merged_pr_is_not_attention():
    result = _build(prs=[_pr(1, "alice", created_day=18, merged_day=19)])

    assert result.attention.review_wanted == []
    assert result.attention.drafts == []


def test_review_wanted_sorted_by_longest_wait():
    result = _build(
        prs=[
            _pr(1, "alice", created_day=19),
            _pr(2, "bob", created_day=10),
            _pr(3, "carol", created_day=15),
        ]
    )

    assert [p.number for p in result.attention.review_wanted] == [2, 3, 1]


def test_stalled_issues_need_an_assignee_past_the_threshold():
    fresh = NOW - timedelta(days=STALLED_ISSUE_DAYS - 1)
    old = NOW - timedelta(days=STALLED_ISSUE_DAYS + 1)

    result = _build(
        issues=[
            _issue(1, "alice", assignees=[SimpleNamespace(login="bob", assigned_at=old)]),
            _issue(2, "alice", assignees=[SimpleNamespace(login="bob", assigned_at=fresh)]),
            _issue(3, "alice", assignees=[_assignee("bob")]),
            _issue(4, "alice"),
        ]
    )

    assert [i.number for i in result.attention.stalled_issues] == [1]
    assert result.attention.stalled_issues[0].assignee_login == "bob"


def test_closed_issue_is_never_stalled():
    old = NOW - timedelta(days=STALLED_ISSUE_DAYS + 1)
    result = _build(
        issues=[
            _issue(
                1,
                "alice",
                closed_day=19,
                assignees=[SimpleNamespace(login="bob", assigned_at=old)],
            )
        ]
    )

    assert result.attention.stalled_issues == []


def test_bot_assignee_is_not_stalled():
    old = NOW - timedelta(days=STALLED_ISSUE_DAYS + 1)
    result = _build(
        issues=[
            _issue(
                1,
                "alice",
                assignees=[SimpleNamespace(login="renovate[bot]", assigned_at=old)],
            )
        ]
    )

    assert result.attention.stalled_issues == []


# --- collaboration -------------------------------------------------------


def test_collaboration_counts_reviewer_to_author():
    result = _build(
        prs=[_pr(1, "alice"), _pr(2, "alice"), _pr(3, "bob")],
        reviews=[
            _review(1, "bob", github_id=11),
            _review(2, "bob", github_id=12),
            _review(3, "alice", github_id=13),
        ],
    )

    assert [(e.reviewer_login, e.author_login, e.count) for e in result.collaboration] == [
        ("bob", "alice", 2),
        ("alice", "bob", 1),
    ]


def test_collaboration_skips_self_reviews_and_bots():
    result = _build(
        prs=[_pr(1, "alice"), _pr(2, "dependabot[bot]")],
        reviews=[
            _review(1, "alice", github_id=11),
            _review(2, "bob", github_id=12),
            _review(1, "coderabbitai[bot]", github_id=13),
        ],
    )

    assert result.collaboration == []


def test_collaboration_ties_are_ordered_deterministically():
    result = _build(
        prs=[_pr(1, "alice"), _pr(2, "bob")],
        reviews=[
            _review(2, "carol", github_id=11),
            _review(1, "carol", github_id=12),
        ],
    )

    assert [e.author_login for e in result.collaboration] == ["alice", "bob"]


# --- themes --------------------------------------------------------------


def test_themes_split_open_and_closed():
    result = _build(
        issues=[
            _issue(1, "alice", labels=["backend"]),
            _issue(2, "alice", labels=["backend"], closed_day=19),
            _issue(3, "bob", labels=["frontend"]),
        ]
    )

    by_label = {t.label: t for t in result.themes}
    assert (by_label["backend"].open_count, by_label["backend"].closed_count) == (1, 1)
    assert (by_label["frontend"].open_count, by_label["frontend"].closed_count) == (1, 0)


def test_themes_exclude_sp_labels():
    result = _build(issues=[_issue(1, "alice", labels=["SP:3", "sp:5", "backend"])])

    assert [t.label for t in result.themes] == ["backend"]


def test_themes_sorted_by_total_then_label():
    result = _build(
        issues=[
            _issue(1, "alice", labels=["b"]),
            _issue(2, "alice", labels=["a", "c"]),
            _issue(3, "alice", labels=["c"]),
        ]
    )

    assert [t.label for t in result.themes] == ["c", "a", "b"]


def test_themes_exclude_bot_authored_issues():
    result = _build(issues=[_issue(1, "renovate[bot]", labels=["deps"])])

    assert result.themes == []


# --- response ------------------------------------------------------------


def test_synced_at_is_passed_through():
    result = _build(synced_at=_dt(20, 9))

    assert result.synced_at == _dt(20, 9)


def test_empty_cache_yields_empty_panels_not_an_error():
    result = _build()

    assert len(result.pulse) == DEFAULT_PULSE_DAYS
    assert result.attention.review_wanted == []
    assert result.attention.drafts == []
    assert result.attention.stalled_issues == []
    assert result.collaboration == []
    assert result.themes == []
    assert result.synced_at is None
