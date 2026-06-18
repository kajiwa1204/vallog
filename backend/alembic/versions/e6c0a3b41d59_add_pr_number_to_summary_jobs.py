"""add_pr_number_to_summary_jobs

Revision ID: e6c0a3b41d59
Revises: d5b9f2a30c48
Create Date: 2026-06-12 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6c0a3b41d59"
down_revision: Union[str, None] = "d5b9f2a30c48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "summary_jobs",
        sa.Column("pr_number", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("summary_jobs", "pr_number")
