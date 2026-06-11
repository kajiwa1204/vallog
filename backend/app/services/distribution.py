import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DistributionEditLog,
    DistributionItem,
    DistributionProposal,
    Project,
    User,
)
from app.repositories.distribution import DistributionRepository
from app.schemas.distribution import (
    EditLogResponse,
    ItemResponse,
    ProposalCreate,
    ProposalResponse,
    ProposalUpdate,
)
from app.schemas.project import CategoryWeights
from app.services import projects as project_service

RATIO_PLACES = Decimal("0.000001")


def _snapshot(items: list[DistributionItem]) -> dict:
    return {
        "items": [
            {"github_login": i.github_login, "ratio": str(i.ratio)}
            for i in sorted(items, key=lambda x: x.github_login)
        ]
    }


async def _ratios_from_scores(
    db: AsyncSession, project: Project, user: User, weights: CategoryWeights
) -> dict[str, Decimal]:
    """分配比率 = 総合スコア ÷ チーム全体の総合スコア合計"""
    scores = await project_service.compute_project_scores(db, project, user)
    totals: dict[str, float] = {}
    for m in scores.members:
        total = (
            weights.activity * m.categories.activity
            + weights.speed * m.categories.speed
            + weights.quality * m.categories.quality
        ) / 100
        totals[m.github_login] = total
    grand = sum(totals.values())
    if grand <= 0:
        equal = Decimal(1) / Decimal(len(totals)) if totals else Decimal(0)
        return {login: equal.quantize(RATIO_PLACES) for login in totals}
    return {
        login: (Decimal(str(v)) / Decimal(str(grand))).quantize(
            RATIO_PLACES, rounding=ROUND_HALF_UP
        )
        for login, v in totals.items()
    }


def _to_response(
    proposal: DistributionProposal,
    creator_login: str,
    avatars: dict[str, str | None],
) -> ProposalResponse:
    total = proposal.total_amount
    return ProposalResponse(
        id=proposal.id,
        title=proposal.title,
        status=proposal.status,
        total_amount=total,
        weights=CategoryWeights(
            activity=proposal.weight_activity,
            speed=proposal.weight_speed,
            quality=proposal.weight_quality,
        ),
        items=[
            ItemResponse(
                github_login=i.github_login,
                avatar_url=avatars.get(i.github_login)
                or f"https://github.com/{i.github_login}.png",
                ratio=i.ratio,
                amount=(
                    (total * i.ratio).quantize(Decimal("0.01"), ROUND_HALF_UP)
                    if total is not None
                    else None
                ),
            )
            for i in sorted(proposal.items, key=lambda x: x.ratio, reverse=True)
        ],
        creator_login=creator_login,
        created_at=proposal.created_at,
        agreed_at=proposal.agreed_at,
    )


async def _creator_login(db: AsyncSession, proposal: DistributionProposal) -> str:
    from app.repositories.user import UserRepository

    creator = await UserRepository(db).get(proposal.created_by)
    return creator.github_login if creator else "unknown"


async def create_proposal(
    db: AsyncSession, project: Project, user: User, payload: ProposalCreate
) -> ProposalResponse:
    weights = CategoryWeights(
        activity=project.weight_activity,
        speed=project.weight_speed,
        quality=project.weight_quality,
    )
    ratios = await _ratios_from_scores(db, project, user, weights)
    if not ratios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="スコア算出対象のメンバーがいないため、分配案を作成できません",
        )
    proposal = DistributionProposal(
        project_id=project.id,
        title=payload.title,
        weight_activity=weights.activity,
        weight_speed=weights.speed,
        weight_quality=weights.quality,
        total_amount=payload.total_amount,
        created_by=user.id,
    )
    proposal.items = [
        DistributionItem(github_login=login, ratio=ratio)
        for login, ratio in ratios.items()
    ]
    await DistributionRepository(db).create(proposal)
    await db.commit()
    avatars = await project_service.registered_member_map(db, project.id)
    return _to_response(proposal, user.github_login, avatars)


async def get_proposal(
    db: AsyncSession, project: Project, proposal_id: uuid.UUID
) -> DistributionProposal:
    proposal = await DistributionRepository(db).get(proposal_id)
    if proposal is None or proposal.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="分配案が見つかりません"
        )
    return proposal


async def update_proposal(
    db: AsyncSession,
    project: Project,
    user: User,
    proposal_id: uuid.UUID,
    payload: ProposalUpdate,
) -> ProposalResponse:
    repo = DistributionRepository(db)
    proposal = await get_proposal(db, project, proposal_id)
    if proposal.status == "agreed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="合意済みの分配案は編集できません",
        )

    before = _snapshot(proposal.items)

    if payload.title is not None:
        proposal.title = payload.title
    if payload.total_amount is not None:
        proposal.total_amount = payload.total_amount

    if payload.weights is not None:
        w = payload.weights
        if w.activity + w.speed + w.quality != 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="重みの合計は100にしてください",
            )
        proposal.weight_activity = w.activity
        proposal.weight_speed = w.speed
        proposal.weight_quality = w.quality
        # 重み変更時はスコアから分配比率を再計算する
        ratios = await _ratios_from_scores(db, project, user, w)
        await repo.replace_items(
            proposal,
            [
                DistributionItem(github_login=login, ratio=ratio)
                for login, ratio in ratios.items()
            ],
        )

    if payload.items is not None:
        total_ratio = sum(i.ratio for i in payload.items)
        if abs(total_ratio - Decimal(1)) > Decimal("0.01"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="分配比率の合計は100%にしてください",
            )
        await repo.replace_items(
            proposal,
            [
                DistributionItem(
                    github_login=i.github_login,
                    ratio=i.ratio.quantize(RATIO_PLACES, ROUND_HALF_UP),
                )
                for i in payload.items
            ],
        )

    after = _snapshot(proposal.items)
    await repo.add_edit_log(
        DistributionEditLog(
            proposal_id=proposal.id,
            edited_by=user.id,
            reason=payload.reason,
            before_items=before,
            after_items=after,
        )
    )
    await db.commit()
    avatars = await project_service.registered_member_map(db, project.id)
    return _to_response(proposal, await _creator_login(db, proposal), avatars)


async def agree_proposal(
    db: AsyncSession, project: Project, user: User, proposal_id: uuid.UUID
) -> ProposalResponse:
    proposal = await get_proposal(db, project, proposal_id)
    if proposal.status == "agreed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="すでに合意済みです"
        )
    proposal.status = "agreed"
    proposal.agreed_at = datetime.now(timezone.utc)
    await db.commit()
    avatars = await project_service.registered_member_map(db, project.id)
    return _to_response(proposal, await _creator_login(db, proposal), avatars)


async def proposal_response(
    db: AsyncSession, project: Project, proposal_id: uuid.UUID
) -> ProposalResponse:
    proposal = await get_proposal(db, project, proposal_id)
    avatars = await project_service.registered_member_map(db, project.id)
    return _to_response(proposal, await _creator_login(db, proposal), avatars)


async def list_edit_logs(
    db: AsyncSession, project: Project, proposal_id: uuid.UUID
) -> list[EditLogResponse]:
    await get_proposal(db, project, proposal_id)
    logs = await DistributionRepository(db).list_edit_logs(proposal_id)
    return [
        EditLogResponse(
            id=log.id,
            editor_login=log.editor.github_login,
            editor_avatar_url=log.editor.avatar_url,
            reason=log.reason,
            before_items=log.before_items,
            after_items=log.after_items,
            created_at=log.created_at,
        )
        for log in logs
    ]
