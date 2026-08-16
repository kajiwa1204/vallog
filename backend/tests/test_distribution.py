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
    repo.delete_proposal = AsyncMock()

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
        {"github_login": "alice", "ratio": "0.6"},
        {"github_login": "bob", "ratio": "0.4"},
    ]
    assert log.after_items["items"] == [
        {"github_login": "alice", "ratio": "0.500000"},
        {"github_login": "bob", "ratio": "0.500000"},
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


async def test_update_items_accepts_rounding_error():
    proposal = _proposal({"a": "0.5", "b": "0.5"})
    repo = _repo_returning(proposal)
    payload = ItemsUpdate(reason="3等分", items=_items(a="0.333", b="0.333", c="0.334"))

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.update_items(_db(), _PROJECT, proposal.id, _USER, payload)

    repo.add_edit_log.assert_awaited()


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
        ("alice", Decimal("0.800000")),
        ("bob", Decimal("0.200000")),
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


async def test_delete_removes_an_unfinalized_proposal():
    proposal = _proposal({"alice": "0.5", "bob": "0.5"})
    repo = _repo_returning(proposal)
    db = _db()

    with patch.object(service, "DistributionRepository", return_value=repo):
        await service.delete_proposal(db, _PROJECT, proposal.id)

    repo.delete_proposal.assert_awaited_once_with(proposal)
    db.commit.assert_awaited()


async def test_delete_rejects_finalized_proposal():
    """確定は「チームで合意した分配の永続化」なので、後から消せてはいけない。
    消せるなら確定に意味がなくなる。"""
    proposal = _proposal({"alice": "1.0"}, finalized=True)
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.delete_proposal(_db(), _PROJECT, proposal.id)

    assert exc.value.status_code == 409
    assert exc.value.code == ErrorCode.DISTRIBUTION_FINALIZED
    repo.delete_proposal.assert_not_awaited()


async def test_delete_rejects_proposal_of_another_project():
    """他プロジェクトの案は存在を伏せて404。IDを総当たりされても消せない。"""
    proposal = _proposal({"alice": "1.0"})
    proposal.project_id = uuid.uuid4()
    repo = _repo_returning(proposal)

    with patch.object(service, "DistributionRepository", return_value=repo):
        with pytest.raises(AppError) as exc:
            await service.delete_proposal(_db(), _PROJECT, proposal.id)

    assert exc.value.status_code == 404
    assert exc.value.code == ErrorCode.DISTRIBUTION_NOT_FOUND
    repo.delete_proposal.assert_not_awaited()


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


# ---------- 金額換算 ----------


def test_amount_is_apportioned_by_ratio():
    assert service.amount_for(Decimal("100000"), Decimal("0.333333")) == Decimal(
        "33333.30"
    )


def test_amount_is_none_without_total():
    assert service.amount_for(None, Decimal("0.5")) is None


# ---------- バリデーション ----------


def test_reason_must_not_be_blank():
    with pytest.raises(ValidationError):
        ItemsUpdate(reason="   ", items=_items(alice="1.0"))
    with pytest.raises(ValidationError):
        ProposalUpdate(reason="   ", name="案X")


def test_proposal_update_requires_at_least_one_change():
    with pytest.raises(ValidationError):
        ProposalUpdate(reason="なにも変えない")


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
