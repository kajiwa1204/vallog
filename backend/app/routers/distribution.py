import uuid

from fastapi import APIRouter, status

from app.models.distribution import DistributionEditLog, DistributionProposal
from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.distribution import (
    DistributionItemResponse,
    EditLogResponse,
    ItemsUpdate,
    ProposalCreate,
    ProposalListItem,
    ProposalResponse,
    ProposalUpdate,
)
from app.schemas.project import CategoryWeights
from app.services import distribution as distribution_service

router = APIRouter(tags=["distributions"])

Avatars = dict[str, str | None]


def _to_response(proposal: DistributionProposal, avatars: Avatars) -> ProposalResponse:
    return ProposalResponse(
        id=proposal.id,
        project_id=proposal.project_id,
        name=proposal.name,
        weights=CategoryWeights(
            activity=proposal.weight_activity,
            speed=proposal.weight_speed,
            quality=proposal.weight_quality,
        ),
        total_amount=proposal.total_amount,
        finalized=proposal.finalized,
        finalized_at=proposal.finalized_at,
        finalized_by_github_login=(
            proposal.finalizer.github_login if proposal.finalizer else None
        ),
        created_by_github_login=(
            proposal.creator.github_login if proposal.creator else None
        ),
        created_at=proposal.created_at,
        # 配分の多い順。画面7の表はそのままランキングとして読める並びにする
        items=[
            DistributionItemResponse(
                github_login=i.github_login,
                avatar_url=avatars.get(i.github_login),
                ratio=i.ratio,
                amount=distribution_service.amount_for(proposal.total_amount, i.ratio),
            )
            for i in sorted(proposal.items, key=lambda i: i.ratio, reverse=True)
        ],
        edit_logs=[_to_edit_log(log, avatars) for log in proposal.edit_logs],
    )


def _to_edit_log(log: DistributionEditLog, avatars: Avatars) -> EditLogResponse:
    editor_login = log.editor.github_login if log.editor else None
    return EditLogResponse(
        id=log.id,
        edited_by_github_login=editor_login,
        edited_by_avatar_url=avatars.get(editor_login) if editor_login else None,
        reason=log.reason,
        before_items=log.before_items,
        after_items=log.after_items,
        created_at=log.created_at,
    )


@router.get(
    "/projects/{project_id}/distributions", response_model=list[ProposalListItem]
)
async def list_distributions(
    project: MemberProject, db: DB, include_deleted: bool = False
):
    """案の一覧。配分値・編集履歴は詳細で取得する。

    include_deleted=true で削除済みも返す。画面7の「分配の記録」が、確定した案と
    削除された案を同じ履歴として並べるために使う（#100 の抑止は削除の痕跡が残ることに
    依存しているので、消したら見えなくなる、にはしない）。
    """
    proposals = await distribution_service.list_proposals(
        db, project.id, include_deleted=include_deleted
    )
    return [
        ProposalListItem(
            id=p.id,
            name=p.name,
            total_amount=p.total_amount,
            finalized=p.finalized,
            finalized_at=p.finalized_at,
            finalized_by_github_login=(
                p.finalizer.github_login if p.finalizer else None
            ),
            created_by_github_login=p.creator.github_login if p.creator else None,
            created_at=p.created_at,
            deleted_at=p.deleted_at,
            deleted_by_github_login=p.deleter.github_login if p.deleter else None,
        )
        for p in proposals
    ]


@router.post(
    "/projects/{project_id}/distributions",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_distribution(
    payload: ProposalCreate, project: MemberProject, user: CurrentUser, db: DB
):
    """分配案を作成する。items省略時はスコアから初期分配比率を算出する。"""
    proposal = await distribution_service.create_proposal(db, project, user, payload)
    return _to_response(proposal, await _avatars(db, project.id))


@router.get(
    "/projects/{project_id}/distributions/{proposal_id}",
    response_model=ProposalResponse,
)
async def get_distribution(proposal_id: uuid.UUID, project: MemberProject, db: DB):
    """分配案の詳細。編集履歴は全員に公開する（画面7のタイムライン表示）。"""
    proposal = await distribution_service.get_proposal(db, project.id, proposal_id)
    return _to_response(proposal, await _avatars(db, project.id))


@router.patch(
    "/projects/{project_id}/distributions/{proposal_id}",
    response_model=ProposalResponse,
)
async def update_distribution(
    proposal_id: uuid.UUID,
    payload: ProposalUpdate,
    project: MemberProject,
    user: CurrentUser,
    db: DB,
):
    """案の名前・報酬総額・重みを更新する（重み変更時は比率をスコアから再計算）。"""
    proposal = await distribution_service.update_proposal(
        db, project, proposal_id, user, payload
    )
    return _to_response(proposal, await _avatars(db, project.id))


@router.patch(
    "/projects/{project_id}/distributions/{proposal_id}/items",
    response_model=ProposalResponse,
)
async def update_distribution_items(
    proposal_id: uuid.UUID,
    payload: ItemsUpdate,
    project: MemberProject,
    user: CurrentUser,
    db: DB,
):
    proposal = await distribution_service.update_items(
        db, project, proposal_id, user, payload
    )
    return _to_response(proposal, await _avatars(db, project.id))


@router.delete(
    "/projects/{project_id}/distributions/{proposal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_distribution(
    proposal_id: uuid.UUID, project: MemberProject, db: DB
):
    """検討中の案を削除する。確定済みの案は 409（合意の記録は消せない）。"""
    await distribution_service.delete_proposal(db, project, proposal_id)


@router.post(
    "/projects/{project_id}/distributions/{proposal_id}/finalize",
    response_model=ProposalResponse,
)
async def finalize_distribution(
    proposal_id: uuid.UUID, project: MemberProject, user: CurrentUser, db: DB
):
    proposal = await distribution_service.finalize(db, project, proposal_id, user)
    return _to_response(proposal, await _avatars(db, project.id))


async def _avatars(db: DB, project_id: uuid.UUID) -> Avatars:
    return await distribution_service.member_avatars(db, project_id)
