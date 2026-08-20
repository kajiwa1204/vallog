import uuid
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_expression

from app.models.distribution import (
    DistributionEditLog,
    DistributionItem,
    DistributionProposal,
)


def unfinalized_exists_query(project_id: uuid.UUID, updated_after: datetime):
    """#100 のスコア開示ゲートを構成するSQL。"""
    last_edit = (
        select(func.max(DistributionEditLog.created_at))
        .where(DistributionEditLog.proposal_id == DistributionProposal.id)
        .correlate(DistributionProposal)
        .scalar_subquery()
    )
    return select(
        exists().where(
            DistributionProposal.project_id == project_id,
            DistributionProposal.finalized.is_(False),
            DistributionProposal.deleted_at.is_(None),
            func.greatest(
                DistributionProposal.created_at,
                func.coalesce(last_edit, DistributionProposal.created_at),
            )
            >= updated_after,
        )
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
        selectinload(DistributionProposal.deleter),
        selectinload(DistributionProposal.edit_logs).selectinload(
            DistributionEditLog.editor
        ),
    )

    async def list_proposals(
        self, project_id: uuid.UUID, include_deleted: bool = False
    ) -> list[DistributionProposal]:
        """案の一覧。既定では削除済みを含めない。

        include_deleted=True は「分配の記録」（確定済みと削除済みの履歴）用。削除は
        物理削除ではないので、記録としては読めるが作業対象の一覧には出さない。
        """
        query = select(DistributionProposal).where(
            DistributionProposal.project_id == project_id
        )
        if not include_deleted:
            query = query.where(DistributionProposal.deleted_at.is_(None))
        allocation_edit_count = (
            select(func.count(DistributionEditLog.id))
            .where(
                DistributionEditLog.proposal_id == DistributionProposal.id,
                DistributionEditLog.before_items["items"]
                != DistributionEditLog.after_items["items"],
            )
            .correlate(DistributionProposal)
            .scalar_subquery()
        )
        rows = await self.db.scalars(
            query.options(
                selectinload(DistributionProposal.creator),
                selectinload(DistributionProposal.finalizer),
                selectinload(DistributionProposal.deleter),
                # 名前・総額だけの編集は除き、配分値が変わったログだけをDBで数える。
                # JSONBスナップショット本体は、開いた案の詳細でのみ取得する。
                with_expression(
                    DistributionProposal.allocation_edit_count,
                    allocation_edit_count,
                ),
            ).order_by(DistributionProposal.created_at.desc())
        )
        return list(rows.all())

    async def get_proposal(
        self, proposal_id: uuid.UUID, *, for_update: bool = False
    ) -> DistributionProposal | None:
        # populate_existing() がないと、同じセッションで先に読んだ案のロード済み関連
        # （finalizer・edit_logs 等）が古いまま返る。確定・調整の直後に読み直す用途が
        # あるため必須
        query = (
            select(DistributionProposal)
            .where(DistributionProposal.id == proposal_id)
            .options(*self._DETAIL_LOADS)
            .execution_options(populate_existing=True)
        )
        if for_update:
            query = query.with_for_update()
        return await self.db.scalar(query)

    async def exists_unfinalized(
        self, project_id: uuid.UUID, updated_after: datetime
    ) -> bool:
        """`updated_after` 以降に動いた未確定の分配案が1件でもあるか。

        スコアの開示判定に使う（#100）。「動いた」は作成か編集で、編集は
        distribution_edit_logs に必ず1件残る（services/distribution.py の
        update_items / update_proposal がどちらもログを書く）。

        作成日時だけを見ないのは、数週間かけて議論している案が途中で非開示に
        落ちてしまうため。逆に最終更新を見ないと、作りっぱなしの案が1件あるだけで
        スコアが永久に開いたままになる。
        """
        query = unfinalized_exists_query(project_id, updated_after)
        return bool(await self.db.scalar(query))

    async def mark_deleted(
        self, proposal: DistributionProposal, user_id: uuid.UUID, at: datetime
    ) -> None:
        """案を削除済みにする（行は残す）。誰がいつ消したかを記録に残すため。"""
        proposal.deleted_at = at
        proposal.deleted_by = user_id
        await self.db.flush()

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
