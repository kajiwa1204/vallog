"""drop github_syncing from projects

Revision ID: c4d2e9f1a2b3
Revises: b3d6f1a9c7e2
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d2e9f1a2b3"
down_revision: Union[str, None] = "b3d6f1a9c7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("projects", "github_syncing")


def downgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("github_syncing", sa.Boolean(), nullable=False, server_default="false"),
    )
