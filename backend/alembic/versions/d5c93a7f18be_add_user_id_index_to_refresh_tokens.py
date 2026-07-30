"""add user_id index to refresh_tokens

再利用検知の全失効（revoke_all_for_user）と期限切れ行の掃除がどちらも
user_id で絞るため、インデックスを張る。

Revision ID: d5c93a7f18be
Revises: a3f1c7e42b90
Create Date: 2026-07-30 10:12:44.512900

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd5c93a7f18be'
down_revision: Union[str, None] = 'a3f1c7e42b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
