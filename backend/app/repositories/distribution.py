import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    DistributionEditLog,
    DistributionItem,
    DistributionProposal,
)


class DistributionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_project(
        self, project_id: uuid.UUID
    ) -> list[DistributionProposal]:
        rows = await self.db.scalars(
            select(DistributionProposal)
            .where(DistributionProposal.project_id == project_id)
            .order_by(DistributionProposal.created_at.desc())
        )
        return list(rows.all())

    async def get(self, proposal_id: uuid.UUID) -> DistributionProposal | None:
        return await self.db.scalar(
            select(DistributionProposal)
            .where(DistributionProposal.id == proposal_id)
            .options(selectinload(DistributionProposal.items))
        )

    async def create(self, proposal: DistributionProposal) -> DistributionProposal:
        self.db.add(proposal)
        await self.db.flush()
        return proposal

    async def replace_items(
        self, proposal: DistributionProposal, items: list[DistributionItem]
    ) -> None:
        proposal.items.clear()
        await self.db.flush()
        proposal.items.extend(items)
        await self.db.flush()

    async def add_edit_log(self, log: DistributionEditLog) -> DistributionEditLog:
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_edit_logs(
        self, proposal_id: uuid.UUID
    ) -> list[DistributionEditLog]:
        rows = await self.db.scalars(
            select(DistributionEditLog)
            .where(DistributionEditLog.proposal_id == proposal_id)
            .options(selectinload(DistributionEditLog.editor))
            .order_by(DistributionEditLog.created_at.desc())
        )
        return list(rows.all())
