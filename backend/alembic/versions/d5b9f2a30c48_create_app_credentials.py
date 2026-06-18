"""create_app_credentials

Revision ID: d5b9f2a30c48
Revises: c4a8e1f29b37
Create Date: 2026-06-12 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5b9f2a30c48"
down_revision: Union[str, None] = "c4a8e1f29b37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_credentials",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("github_client_id", sa.String(), nullable=False),
        sa.Column("github_client_secret_encrypted", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("app_credentials")
