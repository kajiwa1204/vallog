"""services/distribution.py と schemas/distribution.py のユニットテスト。

DB・GitHub APIは使わず、DistributionRepository をモックに差し替えて
手動調整のスナップショット・確定条件・スコアからの初期比率算出を検証する。
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.errors import AppError, ErrorCode
from app.models.distribution import DistributionItem, DistributionProposal
from app.schemas.distribution import (
    DistributionItemInput,
    ItemsUpdate,
    ProposalCreate,
    ProposalUpdate,
)
from app.schemas.project import CategoryWeights
from app.schemas.score import (
    CategoryScores,
    MemberFacts,
    MemberScore,
    ScoreResponse,
)
from app.services import distribution as service

_USER = SimpleNamespace(id=uuid.uuid4(), github_access_token="token")
_PROJECT = SimpleNamespace(
    id=uuid.uuid4(), weight_activity=40, weight_speed=35, weight_quality=25
)


def _proposal(ratios: dict[str, str], finalized: bool = False) -> DistributionProposal:
    return DistributionProposal(
        id=uuid.uuid4(),
        project_id=_PROJECT.id,
        name="案1",
        weight_activity=40,
        weight_speed=35,
        weight_quality=25,
        total_amount=Decimal("100000.00"),
        finalized=finalized,
        deleted_at=None,
        items=[
            DistributionItem(github_login=login, ratio=Decimal(ratio))
            for login, ratio in ratios.items()
        ],
    )


def _repo_returning(proposal: DistributionProposal | None) -> MagicMock:
    repo = MagicMock()
    repo.get_proposal = AsyncMock(return_value=proposal)
    repo.add_edit_log = AsyncMock()
    repo.create_proposal = AsyncMock()
    repo.count_proposals = AsyncMock(return_value=0)
    repo.mark_deleted = AsyncMock()

    async def replace_items(target, items):
        target.items.clear()
        target.items.extend(items)

    repo.replace_items = AsyncMock(side_effect=replace_items)
    return repo


def _db() -> MagicMock:
    db = MagicMock()
    db.commit = AsyncMock()
    return db


def _items(**ratios: str) -> list[DistributionItemInput]:
    return [
        DistributionItemInput(github_login=login, ratio=Decimal(ratio))
        for login, ratio in ratios.items()
    ]


# ---------- 手動調整 ----------


async def test_update_items_logs_before_and_after_snapshots():
    proposal = _proposal({"alice": "0.6", "bob": "0.4"})
    repo = _repo_returning(proposal)
    payload = ItemsUpdate(
        reason="デザイン対応を反映", items=_items(alice="0.5", bob="0.5")
    )

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.update_items(_db(), _PROJECT, proposal.id, _USER, payload)

    log = repo.add_edit_log.await_args.args[0]
    assert log.reason == "デザイン対応を反映"
    assert log.edited_by == _USER.id
    assert log.before_items["items"] == [
        {"github_login": "alice", "ratio": "0.600"},
        {"github_login": "bob", "ratio": "0.400"},
    ]
    assert log.after_items["items"] == [
        {"github_login": "alice", "ratio": "0.500"},
        {"github_login": "bob", "ratio": "0.500"},
    ]
    # 比率以外の状態もタイムラインに出せるようスナップショットに含める
    assert log.after_items["total_amount"] == "100000.00"
    assert log.after_items["weights"] == {"activity": 40, "speed": 35, "quality": 25}


async def test_update_items_replaces_the_member_set():
    """一覧に無いメンバーは案から外れ、新しいログインは分配対象に加わる。"""
    proposal = _proposal({"alice": "0.5", "bob": "0.5"})
    repo = _repo_returning(proposal)
    payload = ItemsUpdate(reason="carolの貢献を追加", items=_items(alice="0.5", carol="0.5"))

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.update_items(_db(), _PROJECT, proposal.id, _USER, payload)

    assert {i.github_login for i in proposal.items} == {"alice", "carol"}


async def test_update_items_rejects_ratios_not_summing_to_one():
    proposal = _proposal({"alice": "0.5", "bob": "0.5"})
    repo = _repo_returning(proposal)
    payload = ItemsUpdate(reason="調整", items=_items(alice="0.5", bob="0.3"))

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.update_items(_db(), _PROJECT, proposal.id, _USER, payload)

    assert exc.value.status_code == 422
    assert exc.value.code == ErrorCode.DISTRIBUTION_RATIO_TOTAL_INVALID
    repo.add_edit_log.assert_not_awaited()


async def test_update_items_accepts_exactly_one():
    """0.1%刻みで合計ちょうど1.0なら通る（画面が送ってくる形）。"""
    proposal = _proposal({"a": "0.5", "b": "0.5"})
    repo = _repo_returning(proposal)
    payload = ItemsUpdate(reason="3等分", items=_items(a="0.333", b="0.333", c="0.334"))

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.update_items(_db(), _PROJECT, proposal.id, _USER, payload)

    repo.add_edit_log.assert_awaited()


@pytest.mark.parametrize("ratios", [
    {"a": "0.333", "b": "0.333", "c": "0.333"},   # 0.999（1刻み不足）
    {"a": "0.334", "b": "0.333", "c": "0.334"},   # 1.001（1刻み超過）
    {"a": "0.500", "b": "0.495"},                  # 0.995（旧許容誤差の境界）
])
async def test_update_items_rejects_any_deviation_from_one(ratios):
    """許容誤差は設けない。

    以前は0.005の窓があり、合計99.5%の案が 200 で通っていた。総額¥300,000なら
    ¥1,500の取りこぼしが記録として確定できてしまう。
    """
    proposal = _proposal({"a": "0.5", "b": "0.5"})
    repo = _repo_returning(proposal)
    payload = ItemsUpdate(reason="調整", items=_items(**ratios))

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.update_items(_db(), _PROJECT, proposal.id, _USER, payload)

    assert exc.value.status_code == 422
    assert exc.value.code == ErrorCode.DISTRIBUTION_RATIO_TOTAL_INVALID
    repo.add_edit_log.assert_not_awaited()


async def test_update_items_rejects_finalized_proposal():
    proposal = _proposal({"alice": "1.0"}, finalized=True)
    repo = _repo_returning(proposal)
    payload = ItemsUpdate(reason="調整", items=_items(alice="1.0"))

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.update_items(_db(), _PROJECT, proposal.id, _USER, payload)

    assert exc.value.status_code == 409
    assert exc.value.code == ErrorCode.DISTRIBUTION_FINALIZED
    assert proposal.items[0].ratio == Decimal("1.0")


async def test_proposal_of_another_project_is_not_found():
    proposal = _proposal({"alice": "1.0"})
    proposal.project_id = uuid.uuid4()
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.finalize(_db(), _PROJECT, proposal.id, _USER)

    assert exc.value.status_code == 404
    assert exc.value.code == ErrorCode.DISTRIBUTION_NOT_FOUND


# ---------- 案の更新（重み・総額） ----------


async def test_update_weights_recomputes_ratios_from_scores():
    proposal = _proposal({"alice": "0.5", "bob": "0.5"})
    repo = _repo_returning(proposal)
    payload = ProposalUpdate(
        reason="スピード重視で再計算",
        weights=CategoryWeights(activity=20, speed=60, quality=20),
    )

    with patch.object(service, "DistributionRepository", return_value=repo):
        with patch.object(
            service.scoring,
            "get_project_scores",
            AsyncMock(return_value=_scores({"alice": 0.8, "bob": 0.2})),
        ) as get_scores:
            await service.update_proposal(
                _db(), _PROJECT, proposal.id, _USER, payload
            )

    assert get_scores.await_args.kwargs["weights"] == payload.weights
    assert proposal.weight_speed == 60
    assert {(i.github_login, i.ratio) for i in proposal.items} == {
        ("alice", Decimal("0.800")),
        ("bob", Decimal("0.200")),
    }
    log = repo.add_edit_log.await_args.args[0]
    assert log.before_items["weights"]["speed"] == 35
    assert log.after_items["weights"]["speed"] == 60


async def test_update_total_amount_is_logged():
    proposal = _proposal({"alice": "1.0"})
    repo = _repo_returning(proposal)
    payload = ProposalUpdate(reason="賞金が確定した", total_amount=Decimal("300000"))

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.update_proposal(_db(), _PROJECT, proposal.id, _USER, payload)

    assert proposal.total_amount == Decimal("300000.00")
    log = repo.add_edit_log.await_args.args[0]
    assert log.before_items["total_amount"] == "100000.00"
    assert log.after_items["total_amount"] == "300000.00"
    assert log.before_items["items"] == log.after_items["items"]


async def test_total_amount_can_be_cleared():
    proposal = _proposal({"alice": "1.0"})
    repo = _repo_returning(proposal)
    payload = ProposalUpdate(reason="割合だけに戻す", total_amount=None)

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.update_proposal(_db(), _PROJECT, proposal.id, _USER, payload)

    assert proposal.total_amount is None
    log = repo.add_edit_log.await_args.args[0]
    assert log.before_items["total_amount"] == "100000.00"
    assert log.after_items["total_amount"] is None


async def test_update_proposal_rejects_finalized_proposal():
    proposal = _proposal({"alice": "1.0"}, finalized=True)
    repo = _repo_returning(proposal)
    payload = ProposalUpdate(reason="改名", name="案X")

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.update_proposal(_db(), _PROJECT, proposal.id, _USER, payload)

    assert exc.value.code == ErrorCode.DISTRIBUTION_FINALIZED
    assert proposal.name == "案1"


# ---------- 確定 ----------


async def test_finalize_marks_proposal_finalized():
    proposal = _proposal({"alice": "0.5", "bob": "0.5"})
    repo = _repo_returning(proposal)
    db = _db()

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.finalize(db, _PROJECT, proposal.id, _USER)

    assert proposal.finalized is True
    assert proposal.finalized_by == _USER.id
    assert proposal.finalized_at is not None
    db.commit.assert_awaited()
    assert repo.get_proposal.await_args_list[0].kwargs == {"for_update": True}


@pytest.mark.parametrize("ratios", [{"alice": "0.6", "bob": "0.3"}, {}])
async def test_finalize_rejects_ratios_not_summing_to_one(ratios):
    proposal = _proposal(ratios)
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.finalize(_db(), _PROJECT, proposal.id, _USER)

    assert exc.value.status_code == 422
    assert exc.value.code == ErrorCode.DISTRIBUTION_RATIO_TOTAL_INVALID
    assert proposal.finalized is False


async def test_finalize_rejects_already_finalized_proposal():
    proposal = _proposal({"alice": "1.0"}, finalized=True)
    proposal.finalized_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.finalize(_db(), _PROJECT, proposal.id, _USER)

    assert exc.value.code == ErrorCode.DISTRIBUTION_FINALIZED
    assert proposal.finalized_at == datetime(2026, 8, 1, tzinfo=timezone.utc)


# ---------- 削除 ----------


async def test_delete_marks_the_proposal_instead_of_removing_it():
    """物理削除にすると、案を作ってスコアを読んで消す、で痕跡がゼロになる。
    #100 の社会的抑止は痕跡が残ることに依存しているので、行は残す。"""
    proposal = _proposal({"alice": "0.5", "bob": "0.5"})
    repo = _repo_returning(proposal)
    db = _db()

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.delete_proposal(db, _PROJECT, proposal.id, _USER)

    target, user_id, _at = repo.mark_deleted.await_args.args
    assert target is proposal
    assert user_id == _USER.id
    db.commit.assert_awaited()
    assert repo.get_proposal.await_args.kwargs == {"for_update": True}


async def test_delete_rejects_finalized_proposal():
    """確定は「チームで合意した分配の永続化」なので、後から消せてはいけない。
    消せるなら確定に意味がなくなる。"""
    proposal = _proposal({"alice": "1.0"}, finalized=True)
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.delete_proposal(_db(), _PROJECT, proposal.id, _USER)

    assert exc.value.status_code == 409
    assert exc.value.code == ErrorCode.DISTRIBUTION_FINALIZED
    repo.mark_deleted.assert_not_awaited()


async def test_deleted_proposal_is_not_found():
    """削除済みは記録として一覧には残るが、取得・編集・確定の対象にはしない。"""
    proposal = _proposal({"alice": "1.0"})
    proposal.deleted_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.get_proposal(_db(), _PROJECT.id, proposal.id)

    assert exc.value.status_code == 404
    assert exc.value.code == ErrorCode.DISTRIBUTION_NOT_FOUND


async def test_finalize_rejects_deleted_proposal():
    proposal = _proposal({"alice": "1.0"})
    proposal.deleted_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.finalize(_db(), _PROJECT, proposal.id, _USER)

    assert exc.value.code == ErrorCode.DISTRIBUTION_NOT_FOUND
    assert proposal.finalized is False


async def test_delete_rejects_deleted_proposal():
    proposal = _proposal({"alice": "1.0"})
    proposal.deleted_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.delete_proposal(_db(), _PROJECT, proposal.id, _USER)

    assert exc.value.code == ErrorCode.DISTRIBUTION_NOT_FOUND
    repo.mark_deleted.assert_not_awaited()


async def test_delete_rejects_proposal_of_another_project():
    """他プロジェクトの案は存在を伏せて404。IDを総当たりされても消せない。"""
    proposal = _proposal({"alice": "1.0"})
    proposal.project_id = uuid.uuid4()
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.delete_proposal(_db(), _PROJECT, proposal.id, _USER)

    assert exc.value.status_code == 404
    assert exc.value.code == ErrorCode.DISTRIBUTION_NOT_FOUND
    repo.mark_deleted.assert_not_awaited()


# ---------- 作成 ----------


async def test_create_rejects_ratios_not_summing_to_one():
    repo = _repo_returning(None)
    payload = ProposalCreate(items=_items(alice="0.7"))

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.create_proposal(_db(), _PROJECT, _USER, payload)

    assert exc.value.code == ErrorCode.DISTRIBUTION_RATIO_TOTAL_INVALID
    repo.create_proposal.assert_not_awaited()


async def test_create_rejects_project_without_scoreable_members():
    repo = _repo_returning(None)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with patch.object(
            service.scoring, "get_project_scores", AsyncMock(return_value=_scores({}))
        ):
            with pytest.raises(AppError) as exc:
                await service.create_proposal(
                    _db(), _PROJECT, _USER, ProposalCreate()
                )

    assert exc.value.status_code == 422
    assert exc.value.code == ErrorCode.DISTRIBUTION_NO_MEMBERS
    repo.create_proposal.assert_not_awaited()


# ---------- 初期分配比率 ----------


def _scores(totals: dict[str, float]) -> ScoreResponse:
    return ScoreResponse(
        weights=CategoryWeights(activity=40, speed=35, quality=25),
        members=[
            MemberScore(
                github_login=login,
                categories=CategoryScores(activity=0.0, speed=0.0, quality=0.0),
                total=total,
                # 初期比率は total だけで決まる。生事実は分配計算に一切効かない
                facts=MemberFacts(
                    story_points_earned=0,
                    pull_requests_authored=0,
                    reviews_submitted=0,
                    pull_requests_reopened=0,
                    avg_review_turnaround_hours=None,
                ),
            )
            for login, total in totals.items()
        ],
    )


async def _ratios_for(totals: dict[str, float]) -> list[tuple[str, Decimal]]:
    weights = CategoryWeights(activity=40, speed=35, quality=25)
    with patch.object(
        service.scoring, "get_project_scores", AsyncMock(return_value=_scores(totals))
    ):
        return await service._score_based_ratios(_db(), _PROJECT, "token", weights)


async def test_score_based_ratios_normalize_to_one():
    ratios = await _ratios_for({"alice": 0.6, "bob": 0.2, "carol": 0.2})
    assert ratios == [
        ("alice", Decimal("0.600000")),
        ("bob", Decimal("0.200000")),
        ("carol", Decimal("0.200000")),
    ]


async def test_score_based_ratios_fall_back_to_equal_split_without_data():
    ratios = await _ratios_for({"alice": 0.0, "bob": 0.0})
    assert ratios == [("alice", Decimal("0.500000")), ("bob", Decimal("0.500000"))]


async def test_score_based_ratios_are_empty_without_members():
    assert await _ratios_for({}) == []


# ---------- 合計をちょうど1.0にする ----------


@pytest.mark.parametrize("members", [2, 3, 4, 5, 6, 7, 8, 9, 11, 13])
async def test_equal_split_always_totals_exactly_one(members):
    """均等割りの丸めで合計が1.0からずれると、作りたての案が確定できない。

    画面は合計100.0%ちょうどでないと保存させないので、サーバが作った案がそのままでは
    確定できない状態になる（3人なら 0.333×3 = 99.9%）。
    """
    ratios = await _ratios_for({f"m{i}": 0.0 for i in range(members)})
    assert sum(r for _, r in ratios) == Decimal(1)
    assert len(ratios) == members


@pytest.mark.parametrize(
    "totals",
    [
        {"a": 1.0, "b": 1.0, "c": 1.0},
        {"a": 0.5, "b": 0.3, "c": 0.2},
        {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3},
        {"a": 7.0, "b": 3.0, "c": 3.0, "d": 3.0},
        {"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0, "e": 1.0, "f": 1.0},
        {"a": 100.0, "b": 0.001},
    ],
)
async def test_score_based_ratios_always_total_exactly_one(totals):
    ratios = await _ratios_for(totals)
    assert sum(r for _, r in ratios) == Decimal(1)


async def test_normalize_keeps_ratios_at_the_display_step():
    """比率の刻みは画面の入力刻み（0.1%）と一致していること。

    ここがずれると、画面は比率を丸めて表示し、丸めた値から金額を計算するので、
    画面の金額とAPIが返す金額が食い違う。
    """
    ratios = await _ratios_for({"a": 2.0, "b": 1.0})
    for _, ratio in ratios:
        assert ratio == ratio.quantize(Decimal("0.001"))


async def test_remainder_goes_to_the_smallest_share():
    """不足分は**配分の少ない順**に配る（最大剰余法ではない）。

    _spread_remainder_to_total_one に渡るのは量子化済みの値で、切り捨て量の情報は
    残っていないため剰余では並べられない。方針を固定して、逆向きの実装に変えたら
    落ちるようにする。

    真値 big 0.6004 / mid 0.2004 / small 0.1992 → 丸めて 0.600 / 0.200 / 0.199（合計0.999）。
    剰余は big=0.0004 / mid=0.0004 / small=0.0002 なので、最大剰余法なら big か mid に
    +0.001 が行く。この実装は small に配る。
    """
    ratios = await _ratios_for({"big": 0.6004, "mid": 0.2004, "small": 0.1992})
    got = dict(ratios)
    assert sum(got.values()) == Decimal(1)
    assert got["small"] == Decimal("0.200"), "不足は配分の少ない人に寄せる"
    assert got["big"] == Decimal("0.600")
    assert got["mid"] == Decimal("0.200")


async def test_normalize_spreads_the_remainder_instead_of_dumping_it():
    """余りは1人に押し付けず、0.1%ずつ複数人に配る。

    6人均等は 0.167×6 = 1.002 で 0.002 の超過。1人から 0.002 引くとその人だけ
    0.165 になり、均等割りのはずが1人だけ 0.2% 低い案ができる。2人から 0.001 ずつ
    引けば全員の差は 0.1% に収まる。
    """
    ratios = dict(await _ratios_for({f"m{i}": 1.0 for i in range(6)}))
    assert sum(ratios.values()) == Decimal(1)
    assert sorted(ratios.values()) == [
        Decimal("0.166"),
        Decimal("0.166"),
        Decimal("0.167"),
        Decimal("0.167"),
        Decimal("0.167"),
        Decimal("0.167"),
    ]
    # 誰か1人に寄せた場合との違いを固定する（最大と最小の差は1刻みまで）
    assert max(ratios.values()) - min(ratios.values()) == Decimal("0.001")


# ---------- 金額換算 ----------


@pytest.mark.parametrize("members", [3, 27])
def test_amounts_sum_to_total_amount(members):
    ratios = [(f"m{i:02}", Decimal("0.037")) for i in range(members)]
    if members == 3:
        ratios = [("a", Decimal("0.333")), ("b", Decimal("0.333")), ("c", Decimal("0.334"))]
    else:
        ratios[-1] = (ratios[-1][0], Decimal("0.038"))

    amounts = service.amounts_for(Decimal("12345"), ratios)

    assert sum((value for value in amounts.values() if value is not None), Decimal(0)) == Decimal("12345.00")


def test_amount_remainder_uses_stable_largest_remainder_order():
    amounts = service.amounts_for(
        Decimal("0.01"),
        [("bob", Decimal("0.5")), ("alice", Decimal("0.5"))],
    )
    assert amounts == {"bob": Decimal("0.00"), "alice": Decimal("0.01")}


def test_amounts_are_none_without_total():
    assert service.amounts_for(None, [("alice", Decimal("1"))]) == {"alice": None}


# ---------- バリデーション ----------


@pytest.mark.parametrize("login", [
    "a" * 40,          # GitHubの上限39文字を超える
    "with space",      # 空白
    "user@example",    # 記号
    "日本語",           # 非ASCII
    "",                # 空
])
def test_item_input_rejects_invalid_github_login(login):
    """DBと画面に任意の文字列が流れ込むのを境界で止める。

    未登録の貢献者を足せるのは意図的な仕様なのでメンバーには縛らないが、
    GitHubのログイン規則（39文字以内・英数字とハイフン）は安定した契約。
    """
    with pytest.raises(ValidationError):
        DistributionItemInput(github_login=login, ratio=Decimal("1.0"))


@pytest.mark.parametrize("login", ["a", "SHOU6439", "some-user", "a" * 39])
def test_item_input_accepts_valid_github_login(login):
    assert DistributionItemInput(github_login=login, ratio=Decimal("1.0")).github_login == login


def test_reason_must_not_be_blank():
    with pytest.raises(ValidationError):
        ItemsUpdate(reason="   ", items=_items(alice="1.0"))
    with pytest.raises(ValidationError):
        ProposalUpdate(reason="   ", name="案X")


def test_proposal_update_requires_at_least_one_change():
    with pytest.raises(ValidationError):
        ProposalUpdate(reason="なにも変えない")
    with pytest.raises(ValidationError):
        ProposalUpdate(reason="名前なし", name=None)


def test_items_update_requires_at_least_one_item():
    with pytest.raises(ValidationError):
        ItemsUpdate(reason="調整", items=[])


def test_ratio_out_of_range_is_rejected():
    with pytest.raises(ValidationError):
        DistributionItemInput(github_login="alice", ratio=Decimal("1.5"))


def test_duplicate_logins_are_rejected():
    items = [
        {"github_login": "alice", "ratio": "0.5"},
        {"github_login": "alice", "ratio": "0.5"},
    ]
    with pytest.raises(ValidationError):
        ItemsUpdate(reason="調整", items=items)
    with pytest.raises(ValidationError):
        ProposalCreate(items=items)
