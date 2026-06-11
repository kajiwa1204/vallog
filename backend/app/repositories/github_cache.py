import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    GitHubIssue,
    GitHubIssueAssignee,
    GitHubPullRequest,
    GitHubReview,
)


class GitHubCacheRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_pull_requests(
        self, project_id: uuid.UUID
    ) -> list[GitHubPullRequest]:
        rows = await self.db.scalars(
            select(GitHubPullRequest)
            .where(GitHubPullRequest.project_id == project_id)
            .order_by(GitHubPullRequest.gh_created_at.desc())
        )
        return list(rows.all())

    async def list_issues(self, project_id: uuid.UUID) -> list[GitHubIssue]:
        rows = await self.db.scalars(
            select(GitHubIssue)
            .where(GitHubIssue.project_id == project_id)
            .options(selectinload(GitHubIssue.assignees))
            .order_by(GitHubIssue.gh_created_at.desc())
        )
        return list(rows.all())

    async def list_reviews(self, project_id: uuid.UUID) -> list[GitHubReview]:
        rows = await self.db.scalars(
            select(GitHubReview)
            .where(GitHubReview.project_id == project_id)
            .order_by(GitHubReview.submitted_at.desc())
        )
        return list(rows.all())

    async def replace_all(
        self,
        project_id: uuid.UUID,
        pull_requests: list[GitHubPullRequest],
        issues: list[GitHubIssue],
        reviews: list[GitHubReview],
    ) -> None:
        """キャッシュを丸ごと入れ替える。差分更新より単純で、件数規模的にも十分。"""
        await self.db.execute(
            delete(GitHubIssueAssignee).where(
                GitHubIssueAssignee.issue_id.in_(
                    select(GitHubIssue.id).where(
                        GitHubIssue.project_id == project_id
                    )
                )
            )
        )
        await self.db.execute(
            delete(GitHubIssue).where(GitHubIssue.project_id == project_id)
        )
        await self.db.execute(
            delete(GitHubPullRequest).where(
                GitHubPullRequest.project_id == project_id
            )
        )
        await self.db.execute(
            delete(GitHubReview).where(GitHubReview.project_id == project_id)
        )
        self.db.add_all(pull_requests)
        self.db.add_all(issues)
        self.db.add_all(reviews)
        await self.db.flush()
