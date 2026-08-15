import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.distribution import (
    DistributionEditLog,
    DistributionItem,
    DistributionProposal,
)


class DistributionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # 案の詳細は items・編集者名・編集履歴まで1レスポンスに詰めるため、遅延ロード
    # （asyncでは例外になる）を避けて必要な関連をまとめて取得する
    _DETAIL_LOADS = (
        selectinload(DistributionProposal.items),
        selectinload(DistributionProposal.creator),
        selectinload(DistributionProposal.finalizer),
        selectinload(DistributionProposal.edit_logs).selectinload(
            DistributionEditLog.editor
        ),
    )

    async def list_proposals(self, project_id: uuid.UUID) -> list[DistributionProposal]:
        rows = await self.db.scalars(
            select(DistributionProposal)
            .where(DistributionProposal.project_id == project_id)
            .options(selectinload(DistributionProposal.creator))
            .order_by(DistributionProposal.created_at.desc())
        )
        return list(rows.all())

    async def get_proposal(self, proposal_id: uuid.UUID) -> DistributionProposal | None:
        # populate_existing() がないと、同じセッションで先に読んだ案のロード済み関連
        # （finalizer・edit_logs 等）が古いまま返る。確定・調整の直後に読み直す用途が
        # あるため必須
        return await self.db.scalar(
            select(DistributionProposal)
            .where(DistributionProposal.id == proposal_id)
            .options(*self._DETAIL_LOADS)
            .execution_options(populate_existing=True)
        )

    async def exists_unfinalized(self, project_id: uuid.UUID) -> bool:
        """未確定の分配案が1件でもあるか。スコアの開示判定に使う（#100）。"""
        return bool(
            await self.db.scalar(
                select(
                    exists().where(
                        DistributionProposal.project_id == project_id,
                        DistributionProposal.finalized.is_(False),
                    )
                )
            )
        )

    async def count_proposals(self, project_id: uuid.UUID) -> int:
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(DistributionProposal)
                .where(DistributionProposal.project_id == project_id)
            )
        ) or 0

    async def create_proposal(
        self, proposal: DistributionProposal
    ) -> DistributionProposal:
        self.db.add(proposal)
        await self.db.flush()
        return proposal

    async def replace_items(
        self, proposal: DistributionProposal, items: list[DistributionItem]
    ) -> None:
        # 削除を先にflushしないと、同じ (proposal_id, github_login) の新旧が
        # 同一トランザクション内で衝突してユニーク制約違反になる
        proposal.items.clear()
        await self.db.flush()
        proposal.items.extend(items)
        await self.db.flush()

    async def add_edit_log(self, log: DistributionEditLog) -> DistributionEditLog:
        self.db.add(log)
        await self.db.flush()
        return log
