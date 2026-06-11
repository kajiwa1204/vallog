import uuid

from fastapi import APIRouter, status

from app.repositories.distribution import DistributionRepository
from app.repositories.user import UserRepository
from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.distribution import (
    EditLogResponse,
    ProposalCreate,
    ProposalListItem,
    ProposalResponse,
    ProposalUpdate,
)
from app.services import distribution as distribution_service

router = APIRouter(tags=["distribution"])


@router.get(
    "/projects/{project_id}/distributions",
    response_model=list[ProposalListItem],
)
async def list_proposals(project: MemberProject, db: DB):
    proposals = await DistributionRepository(db).list_for_project(project.id)
    user_repo = UserRepository(db)
    result = []
    for p in proposals:
        creator = await user_repo.get(p.created_by)
        result.append(
            ProposalListItem(
                id=p.id,
                title=p.title,
                status=p.status,
                total_amount=p.total_amount,
                creator_login=creator.github_login if creator else "unknown",
                created_at=p.created_at,
                agreed_at=p.agreed_at,
            )
        )
    return result


@router.post(
    "/projects/{project_id}/distributions",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_proposal(
    payload: ProposalCreate, project: MemberProject, user: CurrentUser, db: DB
):
    return await distribution_service.create_proposal(db, project, user, payload)


@router.get(
    "/projects/{project_id}/distributions/{proposal_id}",
    response_model=ProposalResponse,
)
async def get_proposal(proposal_id: uuid.UUID, project: MemberProject, db: DB):
    return await distribution_service.proposal_response(db, project, proposal_id)


@router.patch(
    "/projects/{project_id}/distributions/{proposal_id}",
    response_model=ProposalResponse,
)
async def update_proposal(
    proposal_id: uuid.UUID,
    payload: ProposalUpdate,
    project: MemberProject,
    user: CurrentUser,
    db: DB,
):
    return await distribution_service.update_proposal(
        db, project, user, proposal_id, payload
    )


@router.post(
    "/projects/{project_id}/distributions/{proposal_id}/agree",
    response_model=ProposalResponse,
)
async def agree_proposal(
    proposal_id: uuid.UUID, project: MemberProject, user: CurrentUser, db: DB
):
    return await distribution_service.agree_proposal(db, project, user, proposal_id)


@router.get(
    "/projects/{project_id}/distributions/{proposal_id}/logs",
    response_model=list[EditLogResponse],
)
async def list_edit_logs(proposal_id: uuid.UUID, project: MemberProject, db: DB):
    return await distribution_service.list_edit_logs(db, project, proposal_id)
