"""add github_syncing_started_at to projects

Revision ID: b3d6f1a9c7e2
Revises: a8f1e3b6c2d9
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d6f1a9c7e2"
down_revision: Union[str, None] = "a8f1e3b6c2d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("github_syncing_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "github_syncing_started_at")
