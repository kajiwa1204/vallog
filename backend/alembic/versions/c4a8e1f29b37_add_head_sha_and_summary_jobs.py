"""add_head_sha_and_summary_jobs

Revision ID: c4a8e1f29b37
Revises: b7e9f2a1c305
Create Date: 2026-06-12 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4a8e1f29b37'
down_revision: Union[str, None] = 'b7e9f2a1c305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'github_pull_requests',
        sa.Column('head_sha', sa.String(), nullable=True),
    )

    op.create_table(
        'summary_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('github_login', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('total_prs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('done_prs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_summary_jobs_project_login',
        'summary_jobs',
        ['project_id', 'github_login'],
    )


def downgrade() -> None:
    op.drop_index('ix_summary_jobs_project_login', table_name='summary_jobs')
    op.drop_table('summary_jobs')
    op.drop_column('github_pull_requests', 'head_sha')
