import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    GitHubIssue,
    GitHubIssueAssignee,
    GitHubPullRequest,
    GitHubReview,
    Project,
    User,
)
from app.repositories.github_cache import GitHubCacheRepository
from app.repositories.project import ProjectRepository

GITHUB_API = "https://api.github.com"

# 1回の同期で取得する上限。レート制限（5,000 req/h）の予算内に収める
MAX_LIST_PAGES = 5
MAX_EVENT_PAGES = 10
MAX_REVIEW_PRS = 100
REVIEW_CONCURRENCY = 5


class GitHubClient:
    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get(
        self, client: httpx.AsyncClient, path: str, params: dict | None = None
    ) -> httpx.Response:
        res = await client.get(
            f"{GITHUB_API}{path}", params=params, headers=self._headers
        )
        if res.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub APIの認証に失敗しました。再ログインしてください。",
            )
        return res

    async def _get_paginated(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict,
        max_pages: int,
    ) -> list[dict]:
        results: list[dict] = []
        for page in range(1, max_pages + 1):
            res = await self._get(
                client, path, {**params, "per_page": 100, "page": page}
            )
            res.raise_for_status()
            batch = res.json()
            results.extend(batch)
            if len(batch) < 100:
                break
        return results

    async def get_authenticated_user(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await self._get(client, "/user")
            res.raise_for_status()
            return res.json()

    async def list_viewer_repos(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            return await self._get_paginated(
                client,
                "/user/repos",
                {"sort": "pushed", "affiliation": "owner,collaborator,organization_member"},
                max_pages=2,
            )

    async def get_repo(self, owner: str, name: str) -> dict | None:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await self._get(client, f"/repos/{owner}/{name}")
            if res.status_code == 404:
                return None
            res.raise_for_status()
            return res.json()

    async def fetch_pr_diff(self, owner: str, name: str, number: int) -> str:
        """PRのコード差分をdiff形式で取得する。"""
        headers = {**self._headers, "Accept": "application/vnd.github.diff"}
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.get(
                f"{GITHUB_API}/repos/{owner}/{name}/pulls/{number}",
                headers=headers,
            )
            if res.status_code in (401, 403):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="GitHub APIの認証に失敗しました。再ログインしてください。",
                )
            res.raise_for_status()
            return res.text

    async def fetch_repo_data(
        self, owner: str, name: str
    ) -> tuple[list[dict], list[dict], dict[int, list[dict]], list[dict]]:
        """PR・Issue・レビュー・Issueイベントをまとめて取得する。"""
        async with httpx.AsyncClient(timeout=60) as client:
            pulls, issues, events = await asyncio.gather(
                self._get_paginated(
                    client,
                    f"/repos/{owner}/{name}/pulls",
                    {"state": "all", "sort": "created", "direction": "desc"},
                    MAX_LIST_PAGES,
                ),
                self._get_paginated(
                    client,
                    f"/repos/{owner}/{name}/issues",
                    {"state": "all", "sort": "created", "direction": "desc"},
                    MAX_LIST_PAGES,
                ),
                self._get_paginated(
                    client,
                    f"/repos/{owner}/{name}/issues/events",
                    {},
                    MAX_EVENT_PAGES,
                ),
            )

            semaphore = asyncio.Semaphore(REVIEW_CONCURRENCY)

            async def fetch_reviews(number: int) -> tuple[int, list[dict]]:
                async with semaphore:
                    res = await self._get(
                        client,
                        f"/repos/{owner}/{name}/pulls/{number}/reviews",
                        {"per_page": 100},
                    )
                    res.raise_for_status()
                    return number, res.json()

            review_targets = [p["number"] for p in pulls[:MAX_REVIEW_PRS]]
            review_results = await asyncio.gather(
                *(fetch_reviews(n) for n in review_targets)
            )
            reviews_by_pr = {number: revs for number, revs in review_results}

        return pulls, issues, reviews_by_pr, events


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _build_cache_rows(
    project_id: Any,
    pulls: list[dict],
    issues: list[dict],
    reviews_by_pr: dict[int, list[dict]],
    events: list[dict],
) -> tuple[list[GitHubPullRequest], list[GitHubIssue], list[GitHubReview]]:
    assigned_at: dict[tuple[int, str], datetime] = {}
    reopen_counts: dict[int, int] = {}
    for ev in events:
        issue = ev.get("issue") or {}
        number = issue.get("number")
        if number is None:
            continue
        if ev.get("event") == "assigned" and ev.get("assignee"):
            key = (number, ev["assignee"]["login"])
            ts = _parse_dt(ev["created_at"])
            if ts is not None and (key not in assigned_at or ts < assigned_at[key]):
                assigned_at[key] = ts
        elif ev.get("event") == "reopened":
            reopen_counts[number] = reopen_counts.get(number, 0) + 1

    pr_rows = [
        GitHubPullRequest(
            project_id=project_id,
            github_id=p["id"],
            number=p["number"],
            title=p["title"],
            author_login=(p.get("user") or {}).get("login", "unknown"),
            state=p["state"],
            draft=bool(p.get("draft")),
            html_url=p["html_url"],
            body=p.get("body"),
            gh_created_at=_parse_dt(p["created_at"]),
            merged_at=_parse_dt(p.get("merged_at")),
            closed_at=_parse_dt(p.get("closed_at")),
            reopened_count=reopen_counts.get(p["number"], 0),
            head_sha=(p.get("head") or {}).get("sha"),
        )
        for p in pulls
    ]

    issue_rows = []
    for i in issues:
        if "pull_request" in i:
            continue
        row = GitHubIssue(
            project_id=project_id,
            github_id=i["id"],
            number=i["number"],
            title=i["title"],
            author_login=(i.get("user") or {}).get("login", "unknown"),
            state=i["state"],
            labels=[label["name"] for label in i.get("labels", [])],
            html_url=i["html_url"],
            gh_created_at=_parse_dt(i["created_at"]),
            closed_at=_parse_dt(i.get("closed_at")),
        )
        row.assignees = [
            GitHubIssueAssignee(
                login=a["login"],
                assigned_at=assigned_at.get((i["number"], a["login"])),
            )
            for a in i.get("assignees", [])
        ]
        issue_rows.append(row)

    review_rows = [
        GitHubReview(
            project_id=project_id,
            github_id=r["id"],
            pr_number=pr_number,
            reviewer_login=(r.get("user") or {}).get("login", "unknown"),
            state=r["state"],
            body=r.get("body") or "",
            html_url=r["html_url"],
            submitted_at=_parse_dt(r.get("submitted_at")),
        )
        for pr_number, reviews in reviews_by_pr.items()
        for r in reviews
    ]

    return pr_rows, issue_rows, review_rows


async def ensure_cache(
    db: AsyncSession, project: Project, user: User, force: bool = False
) -> Project:
    """TTLが切れていたらGitHubキャッシュを再取得する。

    複数ユーザーの同時リロードによるスタンピードは、行ロックで github_syncing
    フラグを原子的に立てることで防ぐ。取得中は古いキャッシュをそのまま返す。
    """
    now = datetime.now(timezone.utc)
    ttl = settings.github_cache_ttl_seconds

    def is_fresh(p: Project) -> bool:
        return (
            p.github_synced_at is not None
            and (now - p.github_synced_at).total_seconds() < ttl
        )

    if is_fresh(project) and not force:
        return project

    repo = ProjectRepository(db)
    locked = await repo.lock_for_sync(project.id)
    if locked is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if locked.github_syncing or (is_fresh(locked) and not force):
        await db.commit()
        return locked

    locked.github_syncing = True
    await db.commit()

    try:
        client = GitHubClient(user.github_access_token)
        pulls, issues, reviews_by_pr, events = await client.fetch_repo_data(
            locked.repo_owner, locked.repo_name
        )
        pr_rows, issue_rows, review_rows = _build_cache_rows(
            locked.id, pulls, issues, reviews_by_pr, events
        )
        cache_repo = GitHubCacheRepository(db)
        await cache_repo.replace_all(locked.id, pr_rows, issue_rows, review_rows)
        locked.github_synced_at = datetime.now(timezone.utc)
        locked.github_syncing = False
        await db.commit()
    except Exception:
        await db.rollback()
        # 失敗時もフラグを必ず解除する（次のリクエストで再試行できるように）
        unlock = await repo.lock_for_sync(project.id)
        if unlock is not None:
            unlock.github_syncing = False
            await db.commit()
        raise

    return locked
