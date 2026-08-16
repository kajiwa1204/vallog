"""services/scoring.py のスコア計算ロジックのユニットテスト。

キャッシュ済みGitHubデータ（ORMオブジェクト）を SimpleNamespace で模して渡す。DBは使わない。
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError, ErrorCode
from app.services.scoring import (
    SCORE_DISCLOSURE_WINDOW_DAYS,
    _activity_relative,
    _collect_logins,
    _combine_equal,
    _member_facts,
    _quality_values,
    _shares,
    _sp_totals,
    _speed_values,
    _turnaround_values,
    can_disclose_scores,
    compute_scores,
    get_scores_for_disclosure,
)


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=timezone.utc)


def _pr(number, author, *, merged=True, created_day=1, reopened=0):
    return SimpleNamespace(
        number=number,
        author_login=author,
        state="closed" if merged else "open",
        merged_at=_dt(created_day, 12) if merged else None,
        gh_created_at=_dt(created_day),
        reopened_count=reopened,
    )


def _issue(
    number, author, *, sp=None, created_day=1, closed_day=None,
    assignees=(), labels=(), state_reason=None,
):
    return SimpleNamespace(
        number=number,
        author_login=author,
        story_points=sp,
        labels=list(labels),
        state_reason=state_reason,
        gh_created_at=_dt(created_day),
        closed_at=_dt(closed_day) if closed_day else None,
        assignees=[SimpleNamespace(login=a[0], assigned_at=_dt(a[1])) for a in assignees],
    )


def _review(number, reviewer, state, *, submitted_day=1, submitted_hour=1, comments=0, body=""):
    return SimpleNamespace(
        pr_number=number,
        reviewer_login=reviewer,
        state=state,
        submitted_at=_dt(submitted_day, submitted_hour),
        comment_count=comments,
        body=body,
    )


# ---------------------------------------------------------------------------
# _collect_logins
# ---------------------------------------------------------------------------

def test_collect_logins_unions_all_roles_and_drops_bots():
    prs = [_pr(1, "alice")]
    issues = [_issue(10, "bob", assignees=[("carol", 1)])]
    reviews = [_review(1, "dependabot[bot]", "APPROVED")]
    assert _collect_logins(prs, issues, reviews) == {"alice", "bob", "carol"}


def test_collect_logins_includes_registered_members_without_activity():
    """活動のないVallog登録メンバーもダッシュボードから消えないようゼロスコアで含める。"""
    prs = [_pr(1, "alice")]
    assert _collect_logins(prs, [], [], registered_logins=["bob"]) == {"alice", "bob"}


def test_collect_logins_drops_unknown_fallback():
    """services/github.py の _actor_login はアカウント削除等で "unknown" を入れる。
    実在しない貢献者なのでスコア対象にしない。"""
    prs = [_pr(1, "alice"), _pr(2, "unknown")]
    issues = [_issue(10, "unknown", assignees=[("unknown", 1)])]
    reviews = [_review(1, "unknown", "APPROVED")]
    assert _collect_logins(prs, issues, reviews) == {"alice"}


# ---------------------------------------------------------------------------
# _shares
# ---------------------------------------------------------------------------

def test_shares_divides_by_team_total():
    assert _shares({"a": 5, "b": 15}) == {"a": 0.25, "b": 0.75}


def test_shares_returns_none_when_no_signal():
    assert _shares({"a": 0.0, "b": 0.0}) is None


# ---------------------------------------------------------------------------
# _combine_equal
# ---------------------------------------------------------------------------

def test_combine_equal_averages_active_metrics_and_sums_to_one():
    logins = {"a", "b"}
    metrics = [
        {"a": 3, "b": 1},   # shares 0.75 / 0.25
        {"a": 1, "b": 1},   # shares 0.5 / 0.5
        {"a": 0, "b": 0},   # inactive: ignored
    ]
    result = _combine_equal(metrics, logins)
    assert result["a"] == pytest.approx(0.625)
    assert result["b"] == pytest.approx(0.375)
    assert sum(result.values()) == pytest.approx(1.0)


def test_combine_equal_all_inactive_returns_zeros():
    assert _combine_equal([{"a": 0, "b": 0}], {"a", "b"}) == {"a": 0.0, "b": 0.0}


# ---------------------------------------------------------------------------
# _speed_values  (獲得SP ÷ 経過時間)
# ---------------------------------------------------------------------------

def test_speed_values_total_sp_over_total_hours():
    issues = [_issue(10, "alice", sp=3, closed_day=3, assignees=[("alice", 1)])]  # 48h
    assert _speed_values(issues, {"alice"})["alice"] == pytest.approx(3 / 48)


def test_speed_values_neutral_to_task_splitting():
    """総SP÷総時間なので、同じ仕事を分割してもスコアは変わらない
    （SP2×1件と SP1×2件が同じ経過時間合計なら等価）。"""
    single = [_issue(10, "alice", sp=2, closed_day=3, assignees=[("alice", 1)])]  # 2/48
    split = [
        _issue(11, "alice", sp=1, closed_day=2, assignees=[("alice", 1)]),  # 24h
        _issue(12, "alice", sp=1, closed_day=2, assignees=[("alice", 1)]),  # 24h
    ]  # 合計 2SP / 48h
    assert _speed_values(single, {"alice"})["alice"] == pytest.approx(
        _speed_values(split, {"alice"})["alice"]
    )


def test_speed_values_skips_when_no_sp_or_not_closed():
    logins = {"alice"}
    no_sp = [_issue(10, "alice", closed_day=3, assignees=[("alice", 1)])]
    not_closed = [_issue(11, "alice", sp=3, assignees=[("alice", 1)])]
    assert _speed_values(no_sp, logins)["alice"] == 0.0
    assert _speed_values(not_closed, logins)["alice"] == 0.0


def test_speed_values_excludes_not_planned_issues():
    """Close as not planned で中止されたIssueは成果ではないためSPを計上しない。"""
    issues = [_issue(10, "alice", sp=5, closed_day=3, assignees=[("alice", 1)], state_reason="not_planned")]
    assert _speed_values(issues, {"alice"})["alice"] == 0.0


def test_speed_values_counts_state_reason_none_as_completed():
    """state_reason 未取得（NULL、次回同期前の既存キャッシュ）は completed 相当で計上する。"""
    issues = [_issue(10, "alice", sp=3, closed_day=3, assignees=[("alice", 1)], state_reason=None)]
    assert _speed_values(issues, {"alice"})["alice"] == pytest.approx(3 / 48)


def test_speed_values_falls_back_to_issue_creation_when_assigned_at_missing():
    """/issues/events の取得上限で assigned_at が欠けても、獲得SPを捨てずに
    Issue作成時刻を起点に代替する（gh_created_at=1/1, closed_at=1/3 → 48h）。"""
    issue = _issue(10, "alice", sp=3, closed_day=3, assignees=[("alice", 1)])
    issue.assignees[0].assigned_at = None
    assert _speed_values([issue], {"alice"})["alice"] == pytest.approx(3 / 48)


def test_speed_values_prefers_assigned_at_over_creation():
    """assigned_at があればそちらが起点（1/2アサイン → 24h であって 48h ではない）。"""
    issue = _issue(10, "alice", sp=3, closed_day=3, assignees=[("alice", 2)])
    assert _speed_values([issue], {"alice"})["alice"] == pytest.approx(3 / 24)


def test_speed_values_clamps_tiny_elapsed():
    """アサイン直後クローズ（経過0以下）は下限0.1hにクランプして巨大値を防ぐ。"""
    # assigned_at (day 3) == closed_at (day 3, 00:00) → 経過0 → 0.1hにクランプ
    issues = [_issue(10, "alice", sp=3, closed_day=3, assignees=[("alice", 3)])]
    assert _speed_values(issues, {"alice"})["alice"] == pytest.approx(3 / 0.1)


# ---------------------------------------------------------------------------
# _quality_values  (可用性 − 手戻り)
# ---------------------------------------------------------------------------

def test_quality_counts_externally_approved_merged_pr():
    prs = [_pr(1, "alice")]
    reviews = [_review(1, "bob", "APPROVED")]
    assert _quality_values(prs, reviews, {"alice", "bob"})["alice"] == 1.0


def test_quality_ignores_self_approval():
    prs = [_pr(1, "alice")]
    reviews = [_review(1, "alice", "APPROVED")]
    assert _quality_values(prs, reviews, {"alice"})["alice"] == 0.0


def test_quality_subtracts_reopened_and_floors_at_zero():
    prs = [_pr(1, "alice", reopened=2)]
    reviews = [_review(1, "bob", "APPROVED")]  # +1 availability, -2 rework → floored to 0
    assert _quality_values(prs, reviews, {"alice", "bob"})["alice"] == 0.0


def test_quality_rework_is_pr_reopen_only():
    """手戻りはPR再オープンのみ。可用性1・再オープンなし → 満額のまま。
    bugラベルによる帰属減点は廃止した（正しい帰属は #75 で設計）。"""
    prs = [_pr(1, "alice")]
    reviews = [_review(1, "bob", "APPROVED")]
    assert _quality_values(prs, reviews, {"alice", "bob"})["alice"] == 1.0


# ---------------------------------------------------------------------------
# _activity_relative / _turnaround_values  (セルフレビュー除外)
# ---------------------------------------------------------------------------

def test_activity_excludes_self_review_comments():
    """PR作者が自分のPRに付けたコメント（作者名義のCOMMENTEDレビュー）は
    レビュー貢献に数えない。aliceのセルフコメントは無視され、実レビュアーbobのみ残る。"""
    prs = [_pr(1, "alice")]
    reviews = [
        _review(1, "alice", "COMMENTED", comments=3),  # セルフコメント → 無視
        _review(1, "bob", "COMMENTED", comments=1),    # 実レビュー
    ]
    activity = _activity_relative(prs, [], reviews, {"alice", "bob"})
    # レビュー貢献はbobのみ。aliceの活動量は起票(PR1)由来だけで、レビュー分は乗らない
    assert activity["bob"] > 0
    # bobはレビュー貢献シェアを独占するので、レビュー系3指標でaliceを上回る
    assert activity["bob"] > activity["alice"]


def test_turnaround_excludes_self_review():
    """セルフコメントはPR作成直後に付き経過時間ほぼ0の「爆速レビュー」になるため、
    TATから除外する。除外しないとaliceの応答性が不当に跳ね上がる。"""
    prs = [_pr(1, "alice", created_day=1), _pr(2, "bob", created_day=1)]
    reviews = [
        _review(1, "alice", "COMMENTED", submitted_day=1, submitted_hour=1),  # 自PR: 除外対象
        _review(2, "alice", "APPROVED", submitted_day=3, submitted_hour=0),  # 他PRへの通常レビュー(48h)
    ]
    tat = _turnaround_values(prs, reviews, {"alice", "bob"})
    # aliceのTATは他PR(48h)のみで算出される。自PRの1hが混ざれば平均が大きく下がるはず
    assert tat["alice"] == pytest.approx(1 / (1 + 48))


# ---------------------------------------------------------------------------
# compute_scores  (統合: 相対正規化・重み適用・合計1.0)
# ---------------------------------------------------------------------------

def _project(activity=40, speed=35, quality=25):
    return SimpleNamespace(
        weight_activity=activity, weight_speed=speed, weight_quality=quality
    )


def _sample_data():
    prs = [
        _pr(1, "alice", created_day=1, reopened=0),
        _pr(2, "bob", created_day=2, reopened=1),
    ]
    issues = [
        _issue(10, "alice", sp=3, closed_day=3, assignees=[("alice", 1)]),
        _issue(11, "bob", sp=5, closed_day=4, assignees=[("bob", 2)]),
    ]
    reviews = [
        _review(1, "bob", "APPROVED", submitted_day=1, submitted_hour=2, comments=1),
        _review(2, "alice", "APPROVED", submitted_day=2, submitted_hour=4, body="lgtm"),
    ]
    return prs, issues, reviews


def test_compute_scores_totals_sum_to_one():
    result = compute_scores(_project(), *_sample_data())
    assert sum(m.total for m in result.members) == pytest.approx(1.0)


def test_compute_scores_each_category_sums_to_one():
    result = compute_scores(_project(), *_sample_data())
    assert sum(m.categories.activity for m in result.members) == pytest.approx(1.0)
    assert sum(m.categories.speed for m in result.members) == pytest.approx(1.0)
    assert sum(m.categories.quality for m in result.members) == pytest.approx(1.0)


def test_compute_scores_weights_reflected_per_team():
    prs, issues, reviews = _sample_data()
    # 品質重視のチームでは、品質カテゴリで満点(1.0)のaliceが総合で有利になる
    quality_heavy = compute_scores(_project(activity=10, speed=10, quality=80), prs, issues, reviews)
    activity_heavy = compute_scores(_project(activity=80, speed=10, quality=10), prs, issues, reviews)
    alice_q = next(m.total for m in quality_heavy.members if m.github_login == "alice")
    alice_a = next(m.total for m in activity_heavy.members if m.github_login == "alice")
    assert alice_q > alice_a


def test_compute_scores_sorted_by_total_desc():
    result = compute_scores(_project(), *_sample_data())
    totals = [m.total for m in result.members]
    assert totals == sorted(totals, reverse=True)


def test_compute_scores_empty_cache_returns_no_members():
    result = compute_scores(_project(), [], [], [])
    assert result.members == []
    assert result.weights.activity == 40


# ---------------------------------------------------------------------------
# データが無いカテゴリがあっても合計1.0を保つ（重みを有効カテゴリで再正規化）
# ---------------------------------------------------------------------------

def test_compute_scores_totals_sum_to_one_without_sp_labels():
    """SPラベル未運用（画面3のガイダンス前）でもスピードが空になるだけで合計は1.0。"""
    prs, _, reviews = _sample_data()
    issues_no_sp = [_issue(10, "alice", closed_day=3, assignees=[("alice", 1)])]
    result = compute_scores(_project(), prs, issues_no_sp, reviews)
    assert all(m.categories.speed == 0.0 for m in result.members)
    assert sum(m.total for m in result.members) == pytest.approx(1.0)


def test_compute_scores_totals_sum_to_one_without_reviews():
    """Approve運用なし → 品質が空。活動量も一部サブ指標が欠けるが合計は1.0。"""
    prs, issues, _ = _sample_data()
    result = compute_scores(_project(), prs, issues, [])
    assert all(m.categories.quality == 0.0 for m in result.members)
    assert sum(m.total for m in result.members) == pytest.approx(1.0)


def test_compute_scores_inactive_category_preserves_ratios():
    """重みの再正規化は全員を同じ定数で割ることと等価で、分配比率を変えない
    （docs/scoring_design.md: 分配比率 = 総合スコア ÷ 総合スコア合計）。"""
    prs, issues, _ = _sample_data()
    result = compute_scores(_project(), prs, issues, [])  # 品質が空
    totals = {m.github_login: m.total for m in result.members}

    # 重みを再正規化しない場合の素の加重和から算出した比率と一致するはず
    raw = {
        m.github_login: 0.40 * m.categories.activity + 0.35 * m.categories.speed
        for m in result.members
    }
    raw_sum = sum(raw.values())
    for login, expected in ((k, v / raw_sum) for k, v in raw.items()):
        assert totals[login] == pytest.approx(expected)


def test_compute_scores_registered_member_without_activity_scores_zero():
    prs, issues, reviews = _sample_data()
    result = compute_scores(_project(), prs, issues, reviews, registered_logins=["dave"])
    dave = next(m for m in result.members if m.github_login == "dave")
    assert dave.total == 0.0
    assert (dave.categories.activity, dave.categories.speed, dave.categories.quality) == (0.0, 0.0, 0.0)
    # ゼロスコアのメンバーを足しても既存メンバーの相対スコアは変わらない
    assert sum(m.total for m in result.members) == pytest.approx(1.0)


def test_compute_scores_only_activity_has_data():
    """未マージPRが1本だけ＝起票数しか値を持たない状態でも、活動量だけで合計1.0になる。"""
    prs = [_pr(1, "alice", merged=False), _pr(2, "bob", merged=False, created_day=2)]
    result = compute_scores(_project(), prs, [], [])
    assert all(m.categories.speed == 0.0 and m.categories.quality == 0.0 for m in result.members)
    assert sum(m.total for m in result.members) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# スコアの事後開示ゲート（#100）
# ---------------------------------------------------------------------------

def _disclosure_repo(exists_unfinalized: bool) -> MagicMock:
    repo = MagicMock()
    repo.exists_unfinalized = AsyncMock(return_value=exists_unfinalized)
    return repo


@pytest.mark.asyncio
async def test_can_disclose_scores_is_false_without_any_proposal():
    """作業期間中（案が0件）。③事前既知を折るため非開示。"""
    with patch(
        "app.services.scoring.DistributionRepository",
        return_value=_disclosure_repo(False),
    ):
        assert await can_disclose_scores(MagicMock(), uuid.uuid4()) is False


@pytest.mark.asyncio
async def test_can_disclose_scores_is_true_while_a_proposal_is_open():
    """分配を議論している最中だけ開示する。"""
    with patch(
        "app.services.scoring.DistributionRepository",
        return_value=_disclosure_repo(True),
    ):
        assert await can_disclose_scores(MagicMock(), uuid.uuid4()) is True


@pytest.mark.asyncio
async def test_can_disclose_scores_is_false_when_all_proposals_are_finalized():
    """議論が終わったら非開示に戻る。1回目の分配以降ずっと見えたままにすると、
    2回目の作業期間中に③が折れない。"""
    with patch(
        "app.services.scoring.DistributionRepository",
        return_value=_disclosure_repo(False),
    ):
        assert await can_disclose_scores(MagicMock(), uuid.uuid4()) is False


@pytest.mark.asyncio
async def test_get_scores_for_disclosure_rejects_when_not_disclosable():
    project = SimpleNamespace(id=uuid.uuid4())
    with patch(
        "app.services.scoring.DistributionRepository",
        return_value=_disclosure_repo(False),
    ), patch("app.services.scoring.get_project_scores", new=AsyncMock()) as compute:
        with pytest.raises(AppError) as e:
            await get_scores_for_disclosure(MagicMock(), project, "token")

    assert e.value.status_code == 403
    assert e.value.code is ErrorCode.SCORES_NOT_DISCLOSED
    # 拒否するときはGitHub同期もスコア計算も走らせない
    compute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_scores_for_disclosure_returns_scores_when_disclosable():
    project = SimpleNamespace(id=uuid.uuid4())
    expected = object()
    with patch(
        "app.services.scoring.DistributionRepository",
        return_value=_disclosure_repo(True),
    ), patch(
        "app.services.scoring.get_project_scores",
        new=AsyncMock(return_value=expected),
    ):
        assert await get_scores_for_disclosure(MagicMock(), project, "token") is expected


@pytest.mark.asyncio
async def test_can_disclose_scores_asks_only_for_recently_updated_proposals():
    """作りっぱなしの案でスコアが永久に開いたままにならないよう、判定には
    「最終更新がこの時刻以降」という窓を渡す。"""
    repo = _disclosure_repo(True)
    before = datetime.now(timezone.utc)
    with patch("app.services.scoring.DistributionRepository", return_value=repo):
        await can_disclose_scores(MagicMock(), uuid.uuid4())

    cutoff = repo.exists_unfinalized.await_args.args[1]
    # 窓の長さが SCORE_DISCLOSURE_WINDOW_DAYS 日ぶん過去にあること。
    # 定数を変えたときにここが追随する（値をベタ書きしない）
    expected = before - timedelta(days=SCORE_DISCLOSURE_WINDOW_DAYS)
    assert abs((cutoff - expected).total_seconds()) < 5


# ---------------------------------------------------------------------------
# _member_facts（レシート用の生事実・#18）
# ---------------------------------------------------------------------------

def test_member_facts_counts_only_authored_pull_requests():
    """PR件数はPRだけ。活動量スコアの authored はIssue起票と合算しているが、
    事実として並べるときに混ぜると「PR◯本」が読めなくなる。"""
    prs = [_pr(1, "alice"), _pr(2, "alice"), _pr(3, "bob")]
    issues = [_issue(10, "alice"), _issue(11, "alice")]
    facts = _member_facts(prs, issues, [], {"alice", "bob"})
    assert facts["alice"].pull_requests_authored == 2
    assert facts["bob"].pull_requests_authored == 1


def test_member_facts_story_points_go_to_assignees_not_authors():
    """SPは担当者にのみ配る（_sp_totals と同じ経路）。起票しただけでは付かない。

    変化ログの絞り込みはIssueだけ起票者∪担当者なので、ここを取り違えると
    同じ「SP」で母集合が違う数字が並び、分配の席で合わなくなる。
    """
    issues = [_issue(10, "alice", sp=5, closed_day=2, assignees=[("bob", 1)])]
    facts = _member_facts([], issues, [], {"alice", "bob"})
    assert facts["alice"].story_points_earned == 0
    assert facts["bob"].story_points_earned == 5


def test_member_facts_story_points_exclude_not_planned_issues():
    """成果でないクローズは獲得SPに数えない（スピードスコアと同じ除外）。"""
    issues = [
        _issue(10, "alice", sp=3, closed_day=2, assignees=[("alice", 1)]),
        _issue(11, "alice", sp=8, closed_day=2, assignees=[("alice", 1)],
               state_reason="not_planned"),
    ]
    facts = _member_facts([], issues, [], {"alice"})
    assert facts["alice"].story_points_earned == 3


def test_member_facts_story_points_match_speed_score_denominator():
    """獲得SPとスピードスコアが同じ集計から出ていることを固定する。

    _sp_totals を経由しなくなると（＝どちらかが数え直しになると）ここが落ちる。
    """
    issues = [
        _issue(10, "alice", sp=5, closed_day=2, assignees=[("alice", 1)]),
        _issue(11, "bob", sp=1, closed_day=2, assignees=[("bob", 1)]),
    ]
    logins = {"alice", "bob"}
    sp_sum, hours_sum = _sp_totals(issues, logins)
    facts = _member_facts([], issues, [], logins)
    speed = _speed_values(issues, logins)
    for login in logins:
        assert facts[login].story_points_earned == sp_sum[login]
        assert speed[login] == pytest.approx(sp_sum[login] / hours_sum[login])


def test_member_facts_reviews_exclude_self_reviews():
    """PR作者が自分のPRに付けたコメントはレビュー数に数えない（スコアと同じ除外）。"""
    prs = [_pr(1, "alice")]
    reviews = [
        _review(1, "alice", "COMMENTED", comments=1),   # セルフ: 除外
        _review(1, "bob", "APPROVED", submitted_hour=3),
    ]
    facts = _member_facts(prs, [], reviews, {"alice", "bob"})
    assert facts["alice"].reviews_submitted == 0
    assert facts["bob"].reviews_submitted == 1


def test_member_facts_reopened_count_belongs_to_pr_author():
    """手戻りはPR作者に帰属する（_quality_values と同じ帰属）。"""
    prs = [_pr(1, "alice", reopened=2), _pr(2, "bob")]
    facts = _member_facts(prs, [], [], {"alice", "bob"})
    assert facts["alice"].pull_requests_reopened == 2
    assert facts["bob"].pull_requests_reopened == 0


def test_member_facts_avg_turnaround_matches_score_input():
    """平均TATは応答性スコアの逆写像と一致する（_turnaround_totals を共有）。"""
    prs = [_pr(1, "alice"), _pr(2, "alice", created_day=1)]
    reviews = [
        _review(1, "bob", "APPROVED", submitted_hour=2),   # 2時間
        _review(2, "bob", "COMMENTED", submitted_hour=4),  # 4時間
    ]
    logins = {"alice", "bob"}
    facts = _member_facts(prs, [], reviews, logins)
    assert facts["bob"].avg_review_turnaround_hours == pytest.approx(3.0)
    # スコア側は 1/(1+平均時間)。同じ平均を使っている
    assert _turnaround_values(prs, reviews, logins)["bob"] == pytest.approx(1 / 4)


def test_member_facts_avg_turnaround_is_null_without_reviews():
    """0.0 を返すと「即座に返した」と読めてしまう。平均が定義できないことはNULLで言う。"""
    facts = _member_facts([_pr(1, "alice")], [], [], {"alice"})
    assert facts["alice"].avg_review_turnaround_hours is None


def test_compute_scores_attaches_facts_to_every_member():
    prs, issues, reviews = _sample_data()
    result = compute_scores(_project(), prs, issues, reviews, registered_logins=["dave"])
    facts = {m.github_login: m.facts for m in result.members}
    # 活動のない登録メンバーも0埋めの事実を持つ（存在ごと消さない）
    assert facts["dave"].pull_requests_authored == 0
    assert facts["dave"].avg_review_turnaround_hours is None
    assert sum(f.pull_requests_authored for f in facts.values()) == len(prs)
