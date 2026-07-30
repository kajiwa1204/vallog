"""add replaced_by_jti and user_id index to refresh_tokens

Revision ID: d5c93a7f18be
Revises: a3f1c7e42b90
Create Date: 2026-07-30 10:12:44.512900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd5c93a7f18be'
down_revision: Union[str, None] = 'a3f1c7e42b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("replaced_by_jti", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "replaced_by_jti")
