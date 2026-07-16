import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.summary import ContributionSummary, PRSummary


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
    ) -> None:
        # INSERT ... ON CONFLICT DO UPDATE でアトミックに挿入/更新する。
        # get→addの2段構えだと、同一メンバーを対象にした複数ジョブが同時に走った際に
        # UniqueConstraint違反で片方が落ちる（部分ユニークindexはメンバー一括とPR単独の
        # 同時実行を許すため、この競合は実際に起こりうる）。
        stmt = pg_insert(ContributionSummary).values(
            project_id=project_id,
            github_login=github_login,
            content=content,
            context_hash=context_hash,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "github_login"],
            set_={
                "content": content,
                "context_hash": context_hash,
                # server_defaultは挿入時のみ効くため、更新時は明示的に打ち直す
                "generated_at": func.now(),
            },
        )
        await self.db.execute(stmt)


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

    async def upsert(
        self,
        project_id: uuid.UUID,
        pr_number: int,
        author_login: str,
        content: str,
        context_hash: str,
    ) -> None:
        # メンバー一括ジョブとPR単独ジョブが同一PRを同時にupsertしても落ちないよう、
        # INSERT ... ON CONFLICT DO UPDATE でアトミックに書き込む
        stmt = pg_insert(PRSummary).values(
            project_id=project_id,
            pr_number=pr_number,
            author_login=author_login,
            content=content,
            context_hash=context_hash,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "pr_number"],
            set_={
                "author_login": author_login,
                "content": content,
                "context_hash": context_hash,
                "generated_at": func.now(),
            },
        )
        await self.db.execute(stmt)
