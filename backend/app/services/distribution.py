"""分配シミュレーションの案づくり・手動調整・合意確定。

分配額を自動決定しないのが前提（docs/scoring_design.md「分配の最終決定は人間」）。
スコアは初期値と重み変更時の再計算に使うだけで、以降はメンバーが自由に調整する。
ロールによる編集制限は設けず、編集履歴の全員公開で抑止する（docs/data_model.md「認可設計」）。

比率・金額はfloatではなくDecimalで扱う。分配は金額に直結するため、合計100%の判定が
浮動小数の誤差で揺れないようにする。
"""

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.models.distribution import (
    DistributionEditLog,
    DistributionItem,
    DistributionProposal,
)
from app.models.project import Project
from app.models.user import User
from app.repositories.distribution import DistributionRepository
from app.repositories.project import ProjectRepository
from app.schemas.distribution import ItemsUpdate, ProposalCreate, ProposalUpdate
from app.schemas.project import CategoryWeights
from app.services import scoring

# 分配比率の刻み。画面7の入力刻み（0.1%）と一致させる。
#
# 以前は 0.000001（0.0001%）まで保持していたが、**画面がその精度を表現できない**。
# 0.1%刻みでしか編集できないので、画面は比率を丸めて表示し、丸めた値から金額を
# 計算していた。結果、画面の金額とAPIが返す金額が実データで最大¥50ずれ、しかも
# 丸めの和が1にならないと画面の合計が100.0%にならず、作りたての案を確定できなかった
# （3人均等 = 0.333333 × 3 = 99.9%）。
#
# 保存できる精度を画面の精度に合わせることで、この一致を構成上の帰結にする。
# 実際、ユーザーが一度でも配分を保存すれば全比率は0.1%刻みになるので、6桁の精度は
# 「一度も編集されていない案」にしか存在しない見せかけの精度だった。
_RATIO_PLACES = Decimal("0.001")
_AMOUNT_PLACES = Decimal("0.01")
# 合計比率の許容誤差。クライアントが独自に丸めた値を送ってくる場合に備えて残す。
# サーバが生成する比率は _normalize_to_one() でちょうど1になる
_RATIO_TOTAL_TOLERANCE = Decimal("0.005")


async def list_proposals(
    db: AsyncSession, project_id: uuid.UUID
) -> list[DistributionProposal]:
    return await DistributionRepository(db).list_proposals(project_id)


async def get_proposal(
    db: AsyncSession, project_id: uuid.UUID, proposal_id: uuid.UUID
) -> DistributionProposal:
    return await _load_proposal(db, project_id, proposal_id)


async def member_avatars(
    db: AsyncSession, project_id: uuid.UUID
) -> dict[str, str | None]:
    """分配対象のうちVallog登録済みメンバーのアバター。未登録の貢献者は含まれない。"""
    users = await ProjectRepository(db).list_member_users(project_id)
    return {u.github_login: u.avatar_url for u in users}


async def create_proposal(
    db: AsyncSession, project: Project, user: User, payload: ProposalCreate
) -> DistributionProposal:
    repo = DistributionRepository(db)
    weights = payload.weights or CategoryWeights(
        activity=project.weight_activity,
        speed=project.weight_speed,
        quality=project.weight_quality,
    )
    if payload.items is not None:
        ratios = [(i.github_login, _quantize_ratio(i.ratio)) for i in payload.items]
        _reject_if_ratios_do_not_total_one(ratios)
    else:
        ratios = await _score_based_ratios(db, project, user.github_access_token, weights)
    _reject_if_no_members(ratios)

    name = payload.name or f"案{await repo.count_proposals(project.id) + 1}"
    proposal = DistributionProposal(
        project_id=project.id,
        name=name,
        weight_activity=weights.activity,
        weight_speed=weights.speed,
        weight_quality=weights.quality,
        total_amount=_quantize_amount(payload.total_amount),
        created_by=user.id,
        items=[
            DistributionItem(github_login=login, ratio=ratio) for login, ratio in ratios
        ],
    )
    await repo.create_proposal(proposal)
    await db.commit()
    # commit後にrelationshipを触るとlazy loadが走る（asyncでは例外）ため、
    # レスポンスに必要な関連ごと読み直す
    return await _load_proposal(db, project.id, proposal.id)


async def update_items(
    db: AsyncSession,
    project: Project,
    proposal_id: uuid.UUID,
    user: User,
    payload: ItemsUpdate,
) -> DistributionProposal:
    """配分値を手動調整し、変更前後のスナップショットを編集ログに残す。"""
    repo = DistributionRepository(db)
    proposal = await _load_proposal(db, project.id, proposal_id)
    _reject_if_finalized(proposal)

    ratios = [(i.github_login, _quantize_ratio(i.ratio)) for i in payload.items]
    _reject_if_ratios_do_not_total_one(ratios)

    before = _snapshot(proposal)
    await repo.replace_items(
        proposal,
        [DistributionItem(github_login=login, ratio=ratio) for login, ratio in ratios],
    )
    await _log_edit(repo, proposal, user, payload.reason, before)
    await db.commit()
    return await _load_proposal(db, project.id, proposal_id)


async def update_proposal(
    db: AsyncSession,
    project: Project,
    proposal_id: uuid.UUID,
    user: User,
    payload: ProposalUpdate,
) -> DistributionProposal:
    """案の名前・報酬総額・重みを更新する。重みを変えたら分配比率を再計算する。"""
    repo = DistributionRepository(db)
    proposal = await _load_proposal(db, project.id, proposal_id)
    _reject_if_finalized(proposal)

    before = _snapshot(proposal)
    if payload.name is not None:
        proposal.name = payload.name
    if payload.total_amount is not None:
        proposal.total_amount = _quantize_amount(payload.total_amount)
    if payload.weights is not None:
        proposal.weight_activity = payload.weights.activity
        proposal.weight_speed = payload.weights.speed
        proposal.weight_quality = payload.weights.quality
        # 重みは「スコアをどう見るか」の設定なので、手動調整の結果ではなく
        # 新しい重みで計算し直したスコアを配分値に反映する
        ratios = await _score_based_ratios(
            db, project, user.github_access_token, payload.weights
        )
        _reject_if_no_members(ratios)
        await repo.replace_items(
            proposal,
            [
                DistributionItem(github_login=login, ratio=ratio)
                for login, ratio in ratios
            ],
        )

    await _log_edit(repo, proposal, user, payload.reason, before)
    await db.commit()
    return await _load_proposal(db, project.id, proposal_id)


async def finalize(
    db: AsyncSession, project: Project, proposal_id: uuid.UUID, user: User
) -> DistributionProposal:
    """分配案を合意確定して以降の編集を止める。"""
    proposal = await _load_proposal(db, project.id, proposal_id)
    _reject_if_finalized(proposal)
    _reject_if_ratios_do_not_total_one(
        [(item.github_login, item.ratio) for item in proposal.items]
    )

    proposal.finalized = True
    proposal.finalized_at = datetime.now(timezone.utc)
    proposal.finalized_by = user.id
    await db.commit()
    return await _load_proposal(db, project.id, proposal_id)


async def delete_proposal(
    db: AsyncSession, project: Project, proposal_id: uuid.UUID, user: User
) -> None:
    """検討中の案を削除する。**行は消さず、削除済みとして記録に残す。**

    物理削除にしないのは、#100 の社会的抑止が「`created_by` が記録され編集履歴は
    全員に公開されるため、見えるかたちで意図的な行為をする必要がある」ことで成り立って
    いるため。行ごと消せると「案を作る → 全員のスコアを読む → 重みを変えて別の切り口でも
    読む → 削除する」で痕跡がゼロになり（編集ログも ON DELETE CASCADE で道連れ）、
    抑止の根拠そのものが無くなる。誰がいつ何を消したかが残れば、削除も「見えるかたちの
    行為」に留まる。

    **確定済みの案は削除できない。** 確定は「チームで合意した分配をVallog上に永続化」
    した記録であり（docs/screen_design.md 画面7「合意の記録」）、削除済みの印を付ける
    ことすら合意の記録を濁す。

    ロールによる制限は設けない（他の操作と同じ）。守るのは「誰が消せるか」ではなく
    「消しても記録は残る」ほうで、これは編集履歴の全員公開と同じ考え方。
    """
    proposal = await _load_proposal(db, project.id, proposal_id)
    if proposal.finalized:
        raise AppError(
            status.HTTP_409_CONFLICT,
            ErrorCode.DISTRIBUTION_FINALIZED,
            "Finalized distribution proposals cannot be deleted",
        )
    await DistributionRepository(db).mark_deleted(
        proposal, user.id, datetime.now(timezone.utc)
    )
    await db.commit()


def amount_for(total_amount: Decimal | None, ratio: Decimal) -> Decimal | None:
    """報酬総額を比率で按分した金額。総額未入力なら金額は出さない（比率のみ表示）。"""
    if total_amount is None:
        return None
    return (total_amount * ratio).quantize(_AMOUNT_PLACES, rounding=ROUND_HALF_UP)


async def _load_proposal(
    db: AsyncSession, project_id: uuid.UUID, proposal_id: uuid.UUID
) -> DistributionProposal:
    proposal = await DistributionRepository(db).get_proposal(proposal_id)
    # 他プロジェクトの案は存在を伏せて404にする（メンバーシップは project_id 側で検証済み）
    if proposal is None or proposal.project_id != project_id:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.DISTRIBUTION_NOT_FOUND,
            "Distribution proposal not found",
        )
    return proposal


async def _log_edit(
    repo: DistributionRepository,
    proposal: DistributionProposal,
    user: User,
    reason: str,
    before: dict,
) -> None:
    await repo.add_edit_log(
        DistributionEditLog(
            proposal_id=proposal.id,
            edited_by=user.id,
            reason=reason,
            before_items=before,
            after_items=_snapshot(proposal),
        )
    )


def _reject_if_finalized(proposal: DistributionProposal) -> None:
    if proposal.finalized:
        raise AppError(
            status.HTTP_409_CONFLICT,
            ErrorCode.DISTRIBUTION_FINALIZED,
            "Distribution proposal is already finalized",
        )


def _reject_if_no_members(ratios: list[tuple[str, Decimal]]) -> None:
    if not ratios:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorCode.DISTRIBUTION_NO_MEMBERS,
            "No members to distribute to",
        )


def _reject_if_ratios_do_not_total_one(ratios: list[tuple[str, Decimal]]) -> None:
    total = sum((ratio for _, ratio in ratios), Decimal(0))
    if abs(total - Decimal(1)) > _RATIO_TOTAL_TOLERANCE:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorCode.DISTRIBUTION_RATIO_TOTAL_INVALID,
            f"Distribution ratios must sum to 1.0 (got {total})",
        )


def _quantize_ratio(ratio: Decimal) -> Decimal:
    return ratio.quantize(_RATIO_PLACES, rounding=ROUND_HALF_UP)


def _normalize_to_one(
    ratios: list[tuple[str, Decimal]],
) -> list[tuple[str, Decimal]]:
    """丸めた比率の合計をちょうど1.0にする（最大剰余法）。

    各値を独立に丸めると和が1にならない。3人均等なら 0.333×3 = 0.999、6人なら
    0.167×6 = 1.002 になり、**サーバが作った直後の案が確定できない**（画面は合計
    100.0%ちょうどでないと保存させない）。

    余り（または超過分）を、丸めで最も損をした順に1刻みずつ配る。誰かに丸ごと
    押し付けるより差が小さく、同点なら並び順で決まるので結果が安定する。
    """
    if not ratios:
        return ratios

    step = _RATIO_PLACES
    diff = Decimal(1) - sum((ratio for _, ratio in ratios), Decimal(0))
    if diff == 0:
        return ratios

    # 丸めで削られた量が大きい順（超過なら削る量が小さい順）に配る
    count = int(abs(diff) / step)
    order = sorted(range(len(ratios)), key=lambda i: ratios[i][1], reverse=diff < 0)
    adjusted = [ratio for _, ratio in ratios]
    for n in range(count):
        index = order[n % len(order)]
        adjusted[index] += step if diff > 0 else -step
    # 0未満は作らない（比率は ge=0 の契約）
    adjusted = [max(Decimal(0), value) for value in adjusted]
    return [(login, adjusted[i]) for i, (login, _) in enumerate(ratios)]


def _quantize_amount(amount: Decimal | None) -> Decimal | None:
    """DBの桁（Numeric(14,2)）に丸めてから保持する。編集ログのスナップショットが
    保存前後で別の表記（300000 と 300000.00）にならないようにする。
    """
    if amount is None:
        return None
    return amount.quantize(_AMOUNT_PLACES, rounding=ROUND_HALF_UP)


def _snapshot(proposal: DistributionProposal) -> dict:
    """編集ログに残す案の状態。JSONBに入れるためDecimalは文字列にする。"""
    return {
        "items": [
            {"github_login": item.github_login, "ratio": str(item.ratio)}
            for item in sorted(proposal.items, key=lambda i: i.github_login)
        ],
        "total_amount": (
            str(proposal.total_amount) if proposal.total_amount is not None else None
        ),
        "weights": {
            "activity": proposal.weight_activity,
            "speed": proposal.weight_speed,
            "quality": proposal.weight_quality,
        },
    }


async def _score_based_ratios(
    db: AsyncSession, project: Project, access_token: str, weights: CategoryWeights
) -> list[tuple[str, Decimal]]:
    """スコアの総合値をそのまま分配比率にする（docs/scoring_design.md「分配比率 =
    総合スコア ÷ チーム全体の総合スコア合計」）。
    """
    scores = await scoring.get_project_scores(
        db, project, access_token, weights=weights
    )
    grand_total = sum(m.total for m in scores.members)
    if grand_total <= 0:
        # 全カテゴリにデータが無い（同期前・SPラベル未運用など）ケース。全員0のまま作ると
        # 合計1.0にならず確定できない案になるため、均等割りを調整の出発点にする
        count = len(scores.members)
        if count == 0:
            return []
        equal = _quantize_ratio(Decimal(1) / Decimal(count))
        return _normalize_to_one([(m.github_login, equal) for m in scores.members])
    return _normalize_to_one(
        [
            (
                m.github_login,
                _quantize_ratio(Decimal(str(m.total)) / Decimal(str(grand_total))),
            )
            for m in scores.members
        ]
    )
