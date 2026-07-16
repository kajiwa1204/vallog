import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.summary import SummaryJob


class SummaryJobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def expire_stale(
        self,
        project_id: uuid.UUID,
        github_login: str,
        pr_number: int | None,
        threshold: timedelta,
    ) -> None:
        """created_at が threshold より古い pending/running ジョブを failed にする。

        プロセスが SIGKILL/OOM 等（例外を経ない形）で落ちると status='running' の
        ジョブが残り、アクティブジョブの部分ユニークindexが後続を恒久ブロックする。
        github同期の STALE_SYNC_THRESHOLD と同じ発想で、古いジョブを失効させて
        再生成できるようにする。get_active/create と同じスコープ(pr_number)で絞る。
        """
        cutoff = datetime.now(timezone.utc) - threshold
        filters = [
            SummaryJob.project_id == project_id,
            SummaryJob.github_login == github_login,
            SummaryJob.status.in_(["pending", "running"]),
            SummaryJob.created_at < cutoff,
        ]
        if pr_number is None:
            filters.append(SummaryJob.pr_number.is_(None))
        else:
            filters.append(SummaryJob.pr_number == pr_number)

        await self.db.execute(
            update(SummaryJob)
            .where(*filters)
            .values(
                status="failed",
                error="Job expired: process likely terminated before completion",
                finished_at=datetime.now(timezone.utc),
            )
        )

    async def create(
        self,
        project_id: uuid.UUID,
        github_login: str,
        pr_number: int | None = None,
    ) -> SummaryJob:
        job = SummaryJob(
            project_id=project_id,
            github_login=github_login,
            pr_number=pr_number,
            status="pending",
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get(self, job_id: uuid.UUID) -> SummaryJob | None:
        return await self.db.scalar(
            select(SummaryJob).where(SummaryJob.id == job_id)
        )

    async def get_active(
        self,
        project_id: uuid.UUID,
        github_login: str,
        pr_number: int | None = None,
    ) -> SummaryJob | None:
        """pending または running のジョブを返す。

        pr_number=None の場合はメンバー一括ジョブ(pr_number IS NULL)、
        指定時はそのPR単独のアクティブジョブを返す。
        """
        filters = [
            SummaryJob.project_id == project_id,
            SummaryJob.github_login == github_login,
            SummaryJob.status.in_(["pending", "running"]),
        ]
        if pr_number is None:
            filters.append(SummaryJob.pr_number.is_(None))
        else:
            filters.append(SummaryJob.pr_number == pr_number)

        return await self.db.scalar(select(SummaryJob).where(*filters))

    async def list_latest_per_member(
        self, project_id: uuid.UUID
    ) -> list[SummaryJob]:
        """メンバーごとの最新ジョブ1件ずつを返す(メンバー一括ジョブのみ)。

        PostgreSQL の DISTINCT ON を利用して github_login 単位で
        created_at 降順の最新1件に絞る。PR単独ジョブはメンバー一括の
        進捗と混在させないよう除外する。
        """
        rows = await self.db.scalars(
            select(SummaryJob)
            .where(
                SummaryJob.project_id == project_id,
                SummaryJob.pr_number.is_(None),
            )
            .distinct(SummaryJob.github_login)
            .order_by(SummaryJob.github_login, SummaryJob.created_at.desc())
        )
        return list(rows.all())

    async def list_latest_per_pr(
        self, project_id: uuid.UUID, github_login: str
    ) -> dict[int, SummaryJob]:
        """そのメンバーのPR単独ジョブをpr_numberごとに最新1件返す。"""
        rows = await self.db.scalars(
            select(SummaryJob)
            .where(
                SummaryJob.project_id == project_id,
                SummaryJob.github_login == github_login,
                SummaryJob.pr_number.is_not(None),
            )
            .distinct(SummaryJob.pr_number)
            .order_by(SummaryJob.pr_number, SummaryJob.created_at.desc())
        )
        # pr_number IS NOT NULL で絞っているので実行時は常に int だが、
        # job.pr_number の型は int | None。返り値型 dict[int, ...] と揃えるため明示的に除外する
        return {job.pr_number: job for job in rows.all() if job.pr_number is not None}
