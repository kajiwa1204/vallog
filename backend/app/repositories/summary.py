import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContributionSummary


class SummaryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(
        self, project_id: uuid.UUID, github_login: str
    ) -> ContributionSummary | None:
        return await self.db.scalar(
            select(ContributionSummary).where(
                ContributionSummary.project_id == project_id,
                ContributionSummary.github_login == github_login,
            )
        )

    async def list_for_project(
        self, project_id: uuid.UUID
    ) -> list[ContributionSummary]:
        rows = await self.db.scalars(
            select(ContributionSummary).where(
                ContributionSummary.project_id == project_id
            )
        )
        return list(rows.all())

    async def upsert(
        self,
        project_id: uuid.UUID,
        github_login: str,
        content: str,
        context_hash: str,
    ) -> ContributionSummary:
        summary = await self.get(project_id, github_login)
        if summary is None:
            summary = ContributionSummary(
                project_id=project_id,
                github_login=github_login,
                content=content,
                context_hash=context_hash,
            )
            self.db.add(summary)
        else:
            summary.content = content
            summary.context_hash = context_hash
        await self.db.flush()
        return summary
