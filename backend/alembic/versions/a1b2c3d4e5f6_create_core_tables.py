"""create_core_tables

Revision ID: a1b2c3d4e5f6
Revises: ff421b73d564
Create Date: 2026-06-11 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ff421b73d564'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('repo_owner', sa.String(), nullable=False),
        sa.Column('repo_name', sa.String(), nullable=False),
        sa.Column('weight_activity', sa.Integer(), nullable=False),
        sa.Column('weight_speed', sa.Integer(), nullable=False),
        sa.Column('weight_quality', sa.Integer(), nullable=False),
        sa.Column('github_syncing', sa.Boolean(), nullable=False),
        sa.Column('github_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repo_owner', 'repo_name'),
    )
    op.create_table('project_members',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'user_id'),
    )
    op.create_table('invitation_links',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_table('github_pull_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('github_id', sa.BigInteger(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('author_login', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('draft', sa.Boolean(), nullable=False),
        sa.Column('html_url', sa.String(), nullable=False),
        sa.Column('gh_created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reopened_count', sa.Integer(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'number'),
    )
    op.create_table('github_issues',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('github_id', sa.BigInteger(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('author_login', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('labels', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('html_url', sa.String(), nullable=False),
        sa.Column('gh_created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'number'),
    )
    op.create_table('github_issue_assignees',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('issue_id', sa.UUID(), nullable=False),
        sa.Column('login', sa.String(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['issue_id'], ['github_issues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('issue_id', 'login'),
    )
    op.create_table('github_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('github_id', sa.BigInteger(), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('reviewer_login', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('html_url', sa.String(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'github_id'),
    )
    op.create_table('distribution_proposals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('weight_activity', sa.Integer(), nullable=False),
        sa.Column('weight_speed', sa.Integer(), nullable=False),
        sa.Column('weight_quality', sa.Integer(), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('agreed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('distribution_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('proposal_id', sa.UUID(), nullable=False),
        sa.Column('github_login', sa.String(), nullable=False),
        sa.Column('ratio', sa.Numeric(precision=8, scale=6), nullable=False),
        sa.ForeignKeyConstraint(['proposal_id'], ['distribution_proposals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('proposal_id', 'github_login'),
    )
    op.create_table('distribution_edit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('proposal_id', sa.UUID(), nullable=False),
        sa.Column('edited_by', sa.UUID(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('before_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('after_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['proposal_id'], ['distribution_proposals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['edited_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('contribution_summaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('github_login', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('context_hash', sa.String(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'github_login'),
    )


def downgrade() -> None:
    op.drop_table('contribution_summaries')
    op.drop_table('distribution_edit_logs')
    op.drop_table('distribution_items')
    op.drop_table('distribution_proposals')
    op.drop_table('github_reviews')
    op.drop_table('github_issue_assignees')
    op.drop_table('github_issues')
    op.drop_table('github_pull_requests')
    op.drop_table('invitation_links')
    op.drop_table('project_members')
    op.drop_table('projects')
