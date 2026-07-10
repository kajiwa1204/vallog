"""add partial unique indexes to prevent duplicate active summary jobs

Revision ID: c4f8a1e2b9d7
Revises: 3b12d9bb28ff
Create Date: 2026-07-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f8a1e2b9d7'
down_revision: Union[str, None] = '3b12d9bb28ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 同一メンバー/PRに対する pending/running ジョブの二重起動をDBレベルで防ぐ。
    # メンバー一括ジョブ(pr_number IS NULL)とPR単独ジョブ(pr_number IS NOT NULL)で
    # スコープが異なるため、部分ユニークインデックスを2本張る。
    op.create_index(
        'uq_summary_jobs_active_member',
        'summary_jobs',
        ['project_id', 'github_login'],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running') AND pr_number IS NULL"),
    )
    op.create_index(
        'uq_summary_jobs_active_pr',
        'summary_jobs',
        ['project_id', 'github_login', 'pr_number'],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running') AND pr_number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index('uq_summary_jobs_active_pr', table_name='summary_jobs')
    op.drop_index('uq_summary_jobs_active_member', table_name='summary_jobs')
