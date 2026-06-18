"""add_pr_summaries_and_pr_body

Revision ID: b7e9f2a1c305
Revises: a1b2c3d4e5f6
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7e9f2a1c305'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'github_pull_requests',
        sa.Column('body', sa.Text(), nullable=True),
    )

    op.create_table(
        'pr_summaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('author_login', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('context_hash', sa.String(), nullable=False),
        sa.Column(
            'generated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'pr_number'),
    )
    op.create_index(
        'ix_pr_summaries_project_author',
        'pr_summaries',
        ['project_id', 'author_login'],
    )


def downgrade() -> None:
    op.drop_index('ix_pr_summaries_project_author', table_name='pr_summaries')
    op.drop_table('pr_summaries')
    op.drop_column('github_pull_requests', 'body')
