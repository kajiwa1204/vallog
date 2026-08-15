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
    number,
    author,
    *,
    sp=None,
    created_day=1,
    closed_day=None,
    assignees=(),
    title=None,
    state_reason=None,
):
    return SimpleNamespace(
        number=number,
        title=title or f"Issue {number}",
        author_login=author,
        state="closed" if closed_day else "open",
        state_reason=state_reason,
        story_points=sp,
        html_url=f"https://github.com/o/r/issues/{number}",
        gh_created_at=_dt(created_day),
        closed_at=_dt(closed_day) if closed_day else None,
        assignees=[SimpleNamespace(login=a, assigned_at=_dt(created_day)) for a in assignees],
    )


def _review(number, reviewer, state="APPROVED", *, day=2, hour=0, submitted=True, github_id=None):
    review_id = github_id if github_id is not None else number * 1000
    return SimpleNamespace(
        github_id=review_id,
        pr_number=number,
        reviewer_login=reviewer,
        state=state,
        html_url=f"https://github.com/o/r/pull/{number}#pullrequestreview-{review_id}",
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


def test_closed_issue_keeps_completed_and_rejected_apart():
    """却下・重複でのクローズを「片付けた仕事」と同じ closed で並べない。

    #18 で分配の根拠（レシート）として読まれるため、着手せず閉じた起票が完遂した
    Issueと見分けられないと不当な評価になる。
    """
    completed = _issue(10, "bob", closed_day=4, state_reason="completed")
    rejected = _issue(11, "bob", closed_day=4, state_reason="not_planned")
    states = {e.number: e.state for e in build_changelog([], [completed, rejected], []).entries}
    assert states == {10: "closed", 11: "not_planned"}


def test_duplicate_close_is_not_counted_as_completed():
    """「Close as duplicate」も成果ではない。

    GitHubの state_reason は completed/reopened/not_planned/duplicate/null を取る。
    not_planned だけを見ていた頃は重複クローズが「完了」に落ち、そのSPがスコアの
    根拠にも流れ込んでいた。主要OSS 11リポジトリの実測では duplicate は全リポジトリで
    使われていた（3,300件中167件）ので、起こらない想定は置けない。
    """
    duplicate = _issue(12, "bob", closed_day=4, state_reason="duplicate")
    entry = build_changelog([], [duplicate], []).entries[0]
    assert entry.state == "not_planned"


def test_reopened_state_reason_does_not_make_an_open_issue_not_planned():
    """reopened は open にしか付かない。closed 判定を先に見ているので巻き込まれない。"""
    entry = build_changelog([], [_issue(13, "bob", state_reason="reopened")], []).entries[0]
    assert entry.state == "open"


def test_closed_issue_without_state_reason_counts_as_completed():
    """次回同期前の既存キャッシュは state_reason が NULL。completed 相当に倒す。"""
    entry = build_changelog([], [_issue(10, "bob", closed_day=4)], []).entries[0]
    assert entry.state == "closed"


def test_open_issue_is_never_marked_not_planned():
    entry = build_changelog([], [_issue(10, "bob", state_reason="not_planned")], []).entries[0]
    assert entry.state == "open"


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


def test_id_separates_a_pull_request_from_its_own_reviews():
    """number は kind をまたいで衝突するので、一覧のキーには id を使う。"""
    prs = [_pr(91, "alice")]
    entries = build_changelog(prs, [], [_review(91, "bob")]).entries
    assert {e.number for e in entries} == {91}
    assert len({e.id for e in entries}) == 2


def test_id_separates_repeated_reviews_by_the_same_person():
    """同じ人が同じPRに複数回レビューしても、レビュー自身のIDで区別できる。"""
    prs = [_pr(91, "alice")]
    reviews = [
        _review(91, "bob", "COMMENTED", day=2, github_id=1),
        _review(91, "bob", "APPROVED", day=3, github_id=2),
    ]
    review_ids = {e.id for e in build_changelog(prs, [], reviews).entries if e.kind == "review"}
    assert review_ids == {"review:1", "review:2"}


def test_entries_are_sorted_newest_first_and_limited():
    prs = [_pr(n, "alice", created_day=n, merged_day=n) for n in range(1, 6)]
    entries = build_changelog(prs, [], [], limit=3).entries
    assert [e.number for e in entries] == [5, 4, 3]


# ---------------------------------------------------------------------------
# build_changelog: 事実注記
# ---------------------------------------------------------------------------

def test_pr_notes_record_first_review_wait_and_external_review():
    prs = [_pr(1, "alice", created_day=1)]
    reviews = [_review(1, "bob", day=1, hour=5)]
    entries = build_changelog(prs, [], reviews).entries
    notes = next(e for e in entries if e.kind == "pull_request").notes
    assert notes.reviewed_by_others is True
    assert notes.first_review_hours == 5.0


def test_review_notes_record_the_reviewers_own_response_time():
    """PR行の first_review_hours と同じ区間だが、レビュアー側から見た値なので別フィールド。"""
    prs = [_pr(1, "alice", created_day=1)]
    entries = build_changelog(prs, [], [_review(1, "bob", day=2, hour=0)]).entries
    notes = next(e for e in entries if e.kind == "review").notes
    assert notes.response_hours == 24.0
    assert notes.first_review_hours is None


def test_pr_notes_mark_unreviewed_when_only_self_review_exists():
    prs = [_pr(1, "alice", created_day=1)]
    reviews = [_review(1, "alice", "COMMENTED", day=1, hour=5)]
    pr_entry = next(e for e in build_changelog(prs, [], reviews).entries if e.kind == "pull_request")
    assert pr_entry.notes.reviewed_by_others is False
    assert pr_entry.notes.first_review_hours is None


def test_bot_review_does_not_mark_a_pull_request_as_reviewed():
    """注記は必ず一覧上で辿れる、が変化ログの前提。

    botのレビュー行は一覧に出さないので、これを数えると「他者レビュー済み・待ち時間1.0h」と
    書いてあるのに根拠の行がどこにも無い状態になる。scoring.py も bot を除いたログイン集合で
    ループしており数えないため、揃えないと同じデータから画面ごとに違う事実が出る。
    """
    prs = [_pr(2, "alice", created_day=1)]
    reviews = [_review(2, "coderabbitai[bot]", day=1, hour=1)]
    entries = build_changelog(prs, [], reviews).entries
    assert [e.kind for e in entries] == ["pull_request"]
    assert entries[0].notes.reviewed_by_others is False
    assert entries[0].notes.first_review_hours is None


def test_pr_notes_carry_draft_and_reopened_count():
    notes = build_changelog([_pr(1, "alice", draft=True, reopened=2)], [], []).entries[0].notes
    assert (notes.draft, notes.reopened_count) == (True, 2)


def test_issue_notes_leave_pr_only_facts_unset():
    """「非適用」と「意味のあるゼロ」を区別する。Issueに再オープンの概念は適用しない。"""
    notes = build_changelog([], [_issue(10, "bob", sp=5)], []).entries[0].notes
    assert notes.story_points == 5
    assert notes.reopened_count is None
    assert notes.draft is None
    assert notes.reviewed_by_others is None


# ---------------------------------------------------------------------------
# build_changelog: 除外ルール
# ---------------------------------------------------------------------------

def test_bot_and_unknown_activity_is_dropped():
    prs = [_pr(1, "dependabot[bot]"), _pr(2, "alice")]
    issues = [_issue(10, "unknown")]
    reviews = [_review(2, "dependabot[bot]")]
    entries = build_changelog(prs, issues, reviews).entries
    assert [(e.kind, e.number) for e in entries] == [("pull_request", 2)]


def test_human_review_on_a_bot_pull_request_is_kept():
    """除外はレビュアー本人にだけかける。対象PRの作者がbotでもレビューは残す。

    レビューは責任を伴う実労働で、依存更新PRのレビューも例外ではない。ここを落とすと
    セキュリティ更新を丁寧に見ている人の仕事が #18 の分配根拠から消える。
    bot作者のPR行自体は落ちるので、レビュー行だけが並ぶ状態になるのは意図通り。
    """
    prs = [_pr(50, "dependabot[bot]", title="Bump next from 15.4.2 to 15.5.21")]
    entries = build_changelog(prs, [], [_review(50, "alice")]).entries
    assert [(e.kind, e.actor_login) for e in entries] == [("review", "alice")]
    assert entries[0].title == "Bump next from 15.4.2 to 15.5.21"


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


def test_empty_member_is_treated_as_no_filter():
    """`?member=` は FastAPI では "" になる。絞り込むと0件になり「データが無い」に見える。"""
    prs = [_pr(1, "alice"), _pr(2, "bob")]
    entries = build_changelog(prs, [], [], member="").entries
    assert {e.number for e in entries} == {1, 2}


# ---------------------------------------------------------------------------
# build_changelog: 打ち切り
# ---------------------------------------------------------------------------

def test_has_more_is_true_when_entries_are_truncated():
    prs = [_pr(n, "alice", created_day=n) for n in range(1, 6)]
    res = build_changelog(prs, [], [], limit=3)
    assert (len(res.entries), res.has_more) == (3, True)


def test_has_more_is_false_when_the_result_fits_exactly():
    """ちょうど limit 件のときに True を返すと、フロントが空の「もっと見る」を出す。"""
    prs = [_pr(n, "alice", created_day=n) for n in range(1, 4)]
    res = build_changelog(prs, [], [], limit=3)
    assert (len(res.entries), res.has_more) == (3, False)


# --- Issue行の担当者 -------------------------------------------------------


def test_issue_entry_carries_its_assignees():
    result = build_changelog([], [_issue(1, "alice", assignees=["bob", "carol"])], [])

    assert result.entries[0].notes.assignee_logins == ["bob", "carol"]


def test_issue_assignees_are_sorted_for_a_stable_display():
    result = build_changelog([], [_issue(1, "alice", assignees=["zoe", "bob"])], [])

    assert result.entries[0].notes.assignee_logins == ["bob", "zoe"]


def test_issue_without_assignees_reports_an_empty_list_not_none():
    """「誰も持っていない」は意味のある事実なので、非適用(None)とは区別する。"""
    result = build_changelog([], [_issue(1, "alice")], [])

    assert result.entries[0].notes.assignee_logins == []


def test_pr_and_review_rows_have_no_assignee_field():
    """Issue以外には担当の概念を適用しない（0や空リストを入れると事実として偽になる）。"""
    prs = [_pr(1, "alice")]
    reviews = [_review(1, "bob")]

    result = build_changelog(prs, [], reviews)

    for entry in result.entries:
        assert entry.notes.assignee_logins is None


def test_assignee_only_member_can_tell_why_the_row_is_in_their_list():
    """担当しか関わっていない人で絞ったとき、行が「誰の何か」を持っている。

    修正前は actor_login（起票者）しか無く、samunail で絞ると SHOU6439 の名前だけが
    並んで「その人が起票した」と読めていた。
    """
    issues = [_issue(1, "SHOU6439", assignees=["samunail"])]

    result = build_changelog([], issues, [], member="samunail")

    entry = result.entries[0]
    assert entry.actor_login == "SHOU6439"
    assert entry.notes.assignee_logins == ["samunail"]


def test_bot_assignees_are_kept_as_a_fact():
    """担当は「GitHub上でそのIssueに誰が付いているか」の事実。

    除くと画面の「担当」がGitHubの表示と食い違う。絞り込みの候補（roster）とは役割が違う。
    """
    result = build_changelog([], [_issue(1, "alice", assignees=["copilot[bot]"])], [])

    assert result.entries[0].notes.assignee_logins == ["copilot[bot]"]
