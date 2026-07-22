"""add state_reason to github_issues

Revision ID: a3f1c7e42b90
Revises: c4f8a1e2b9d7
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c7e42b90'
down_revision: Union[str, None] = 'c4f8a1e2b9d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # nullable: 既存キャッシュ行は次回同期まで state_reason 未取得。スコア側は
    # not_planned のみ除外し、NULL は completed 相当（従来どおり計上）として扱う
    op.add_column('github_issues', sa.Column('state_reason', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('github_issues', 'state_reason')
