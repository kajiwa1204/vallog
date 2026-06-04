"""create_users_table

Revision ID: ff421b73d564
Revises: 
Create Date: 2026-06-02 06:48:59.851869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff421b73d564'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('github_id', sa.BigInteger(), nullable=False),
    sa.Column('github_login', sa.String(), nullable=False),
    sa.Column('github_access_token', sa.String(), nullable=False),
    sa.Column('avatar_url', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('github_id'),
    sa.UniqueConstraint('github_login')
    )


def downgrade() -> None:
    op.drop_table('users')
