import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContributionSummary, PRSummary


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
            # server_defaultは挿入時のみ効くため、再生成時は明示的に日時を更新する
            summary.generated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return summary


class PRSummaryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, project_id: uuid.UUID, pr_number: int) -> PRSummary | None:
        return await self.db.scalar(
            select(PRSummary).where(
                PRSummary.project_id == project_id,
                PRSummary.pr_number == pr_number,
            )
        )

    async def list_for_author(
        self, project_id: uuid.UUID, author_login: str
    ) -> list[PRSummary]:
        rows = await self.db.scalars(
            select(PRSummary)
            .where(
                PRSummary.project_id == project_id,
                PRSummary.author_login == author_login,
            )
            .order_by(PRSummary.pr_number.asc())
        )
        return list(rows.all())

    async def list_for_project(self, project_id: uuid.UUID) -> list[PRSummary]:
        rows = await self.db.scalars(
            select(PRSummary).where(PRSummary.project_id == project_id)
        )
        return list(rows.all())

    async def upsert(
        self,
        project_id: uuid.UUID,
        pr_number: int,
        author_login: str,
        content: str,
        context_hash: str,
    ) -> PRSummary:
        summary = await self.get(project_id, pr_number)
        if summary is None:
            summary = PRSummary(
                project_id=project_id,
                pr_number=pr_number,
                author_login=author_login,
                content=content,
                context_hash=context_hash,
            )
            self.db.add(summary)
        else:
            summary.content = content
            summary.context_hash = context_hash
            summary.generated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return summary
