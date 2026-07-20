import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.github_cache import (
    GitHubIssue,
    GitHubIssueAssignee,
    GitHubPullRequest,
    GitHubReview,
)

PullRequestState = Literal["open", "closed"]
IssueState = Literal["open", "closed"]
ReviewState = Literal["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"]


@dataclass
class PullRequestData:
    github_id: int
    number: int
    title: str
    body: str | None
    head_sha: str | None
    author_login: str
    state: PullRequestState
    draft: bool
    html_url: str
    gh_created_at: datetime
    merged_at: datetime | None
    closed_at: datetime | None
    reopened_count: int


@dataclass
class AssigneeData:
    login: str
    assigned_at: datetime | None


@dataclass
class IssueData:
    github_id: int
    number: int
    title: str
    author_login: str
    state: IssueState
    state_reason: str | None
    labels: list[str]
    story_points: int | None
    html_url: str
    gh_created_at: datetime
    closed_at: datetime | None
    assignees: list[AssigneeData] = field(default_factory=list)


@dataclass
class ReviewData:
    github_id: int
    pr_number: int
    reviewer_login: str
    state: ReviewState
    body: str
    comment_count: int
    html_url: str
    submitted_at: datetime | None


class GitHubCacheRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_pull_requests(self, project_id: uuid.UUID) -> list[GitHubPullRequest]:
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

    async def upsert_pull_requests(self, project_id: uuid.UUID, rows: list[PullRequestData]) -> None:
        if not rows:
            return
        values = [
            {
                "id": uuid.uuid4(),
                "project_id": project_id,
                "github_id": r.github_id,
                "number": r.number,
                "title": r.title,
                "body": r.body,
                "head_sha": r.head_sha,
                "author_login": r.author_login,
                "state": r.state,
                "draft": r.draft,
                "html_url": r.html_url,
                "gh_created_at": r.gh_created_at,
                "merged_at": r.merged_at,
                "closed_at": r.closed_at,
                "reopened_count": r.reopened_count,
            }
            for r in rows
        ]
        stmt = pg_insert(GitHubPullRequest).values(values)
        update_cols = {
            c: stmt.excluded[c]
            for c in (
                "github_id",
                "title",
                "body",
                "head_sha",
                "author_login",
                "state",
                "draft",
                "html_url",
                "gh_created_at",
                "merged_at",
                "closed_at",
                "reopened_count",
            )
        }
        update_cols["fetched_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=[GitHubPullRequest.project_id, GitHubPullRequest.number],
            set_=update_cols,
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def upsert_reviews(self, project_id: uuid.UUID, rows: list[ReviewData]) -> None:
        if not rows:
            return
        values = [
            {
                "id": uuid.uuid4(),
                "project_id": project_id,
                "github_id": r.github_id,
                "pr_number": r.pr_number,
                "reviewer_login": r.reviewer_login,
                "state": r.state,
                "body": r.body,
                "comment_count": r.comment_count,
                "html_url": r.html_url,
                "submitted_at": r.submitted_at,
            }
            for r in rows
        ]
        stmt = pg_insert(GitHubReview).values(values)
        update_cols = {
            c: stmt.excluded[c]
            for c in (
                "pr_number",
                "reviewer_login",
                "state",
                "body",
                "comment_count",
                "html_url",
                "submitted_at",
            )
        }
        update_cols["fetched_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=[GitHubReview.project_id, GitHubReview.github_id],
            set_=update_cols,
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def upsert_issues(self, project_id: uuid.UUID, rows: list[IssueData]) -> None:
        if not rows:
            return
        # sort=created でページングする間にissueが増減すると、稀に同じnumberが2ページに
        # またがって重複しうる。ON CONFLICT DO UPDATEは同一文内で同じ行を2度更新できず
        # エラーになるため、事前に number で重複排除する（後勝ち）
        rows = list({r.number: r for r in rows}.values())
        values = [
            {
                "id": uuid.uuid4(),
                "project_id": project_id,
                "github_id": r.github_id,
                "number": r.number,
                "title": r.title,
                "author_login": r.author_login,
                "state": r.state,
                "state_reason": r.state_reason,
                "labels": r.labels,
                "story_points": r.story_points,
                "html_url": r.html_url,
                "gh_created_at": r.gh_created_at,
                "closed_at": r.closed_at,
            }
            for r in rows
        ]
        stmt = pg_insert(GitHubIssue).values(values)
        update_cols = {
            c: stmt.excluded[c]
            for c in (
                "github_id",
                "title",
                "author_login",
                "state",
                "state_reason",
                "labels",
                "story_points",
                "html_url",
                "gh_created_at",
                "closed_at",
            )
        }
        update_cols["fetched_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=[GitHubIssue.project_id, GitHubIssue.number],
            set_=update_cols,
        ).returning(GitHubIssue.id, GitHubIssue.number)
        result = await self.db.execute(stmt)
        id_by_number: dict[int, uuid.UUID] = {number: issue_id for issue_id, number in result.all()}

        # assigneeは他テーブルと違い真のupsertにせず削除→再挿入で洗い替える。PR/Issueの行id安定性は
        # 将来のpr_summaries等からの参照を見据えたものだが、assigneeの集合自体は「現在誰がアサイン
        # されているか」だけが意味を持ち、assigned_atはissueイベントから毎回決定的に再計算されるため、
        # idが同期のたびに変わっても情報は失われない
        issue_ids = list(id_by_number.values())
        if issue_ids:
            await self.db.execute(
                delete(GitHubIssueAssignee).where(GitHubIssueAssignee.issue_id.in_(issue_ids))
            )

        assignee_values = [
            {
                "id": uuid.uuid4(),
                "issue_id": id_by_number[r.number],
                "login": a.login,
                "assigned_at": a.assigned_at,
            }
            for r in rows
            for a in r.assignees
        ]
        if assignee_values:
            await self.db.execute(pg_insert(GitHubIssueAssignee).values(assignee_values))

        await self.db.flush()
