"""soft delete distribution proposals and index fks

分配案の削除を物理削除からソフト削除に変える。

物理削除だと、案を作ってスコアを読み、重みを変えて別の切り口でも読み、削除する、で
痕跡がまったく残らない（編集ログも ON DELETE CASCADE で道連れになる）。#100 は
「created_by が記録され編集履歴は全員に公開されるため、見えるかたちで意図的な行為を
する必要がある」ことを社会的抑止の根拠にしているので、削除がその根拠を消してしまう。

あわせて外部キーにインデックスを張る。PostgreSQL は FK に自動でインデックスを作らず、
スコアの開示判定（未確定案ごとに編集ログの最新を引く相関サブクエリ）と案一覧が
どちらもこの2列で絞る。

Revision ID: d140dad67ff7
Revises: 1e6d2302ba15
Create Date: 2026-08-16 22:31:04.118420

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd140dad67ff7'
down_revision: Union[str, None] = '1e6d2302ba15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "distribution_proposals",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "distribution_proposals",
        sa.Column("deleted_by", sa.UUID(as_uuid=True), nullable=True),
    )
    # 削除した人が退会してもレコードは残す（誰がいつ消したかが抑止の根拠のため）
    op.create_foreign_key(
        "distribution_proposals_deleted_by_fkey",
        "distribution_proposals",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_distribution_proposals_project_id",
        "distribution_proposals",
        ["project_id"],
    )
    op.create_index(
        "ix_distribution_edit_logs_proposal_id",
        "distribution_edit_logs",
        ["proposal_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_distribution_edit_logs_proposal_id", "distribution_edit_logs")
    op.drop_index("ix_distribution_proposals_project_id", "distribution_proposals")
    op.drop_constraint(
        "distribution_proposals_deleted_by_fkey",
        "distribution_proposals",
        type_="foreignkey",
    )
    op.drop_column("distribution_proposals", "deleted_by")
    op.drop_column("distribution_proposals", "deleted_at")
