"""add distribution tables

Revision ID: d5c2a7f4b613
Revises: a3f1c7e42b90
Create Date: 2026-08-02 10:12:33.108422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd5c2a7f4b613'
down_revision: Union[str, None] = 'a3f1c7e42b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('distribution_proposals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('weight_activity', sa.Integer(), nullable=False),
    sa.Column('weight_speed', sa.Integer(), nullable=False),
    sa.Column('weight_quality', sa.Integer(), nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('finalized', sa.Boolean(), nullable=False),
    sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finalized_by', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['finalized_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('distribution_items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('proposal_id', sa.UUID(), nullable=False),
    sa.Column('github_login', sa.String(), nullable=False),
    sa.Column('ratio', sa.Numeric(precision=8, scale=6), nullable=False),
    sa.ForeignKeyConstraint(['proposal_id'], ['distribution_proposals.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('proposal_id', 'github_login')
    )
    op.create_table('distribution_edit_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('proposal_id', sa.UUID(), nullable=False),
    sa.Column('edited_by', sa.UUID(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('before_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('after_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['proposal_id'], ['distribution_proposals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['edited_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('distribution_edit_logs')
    op.drop_table('distribution_items')
    op.drop_table('distribution_proposals')
