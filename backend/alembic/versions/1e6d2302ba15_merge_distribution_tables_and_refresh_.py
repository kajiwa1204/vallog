"""merge distribution tables and refresh token index

分配テーブル（d5c2a7f4b613）とrefresh_tokensのインデックス（d5c93a7f18be）が、
どちらも a3f1c7e42b90 を親とする別々のPRで追加されたため head が2つになっていた。
`alembic upgrade head` は "Multiple head revisions are present" で失敗し、新しい環境で
分配テーブルが作られない（画面7が動かない）。

スキーマ変更は無く、履歴を1本に戻すだけのマージリビジョン。

Revision ID: 1e6d2302ba15
Revises: d5c93a7f18be, d5c2a7f4b613
Create Date: 2026-08-16 10:37:26.370443

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '1e6d2302ba15'
down_revision: Union[str, None] = ('d5c93a7f18be', 'd5c2a7f4b613')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
