from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.project import Project
from app.repositories.project import ProjectRepository

GITHUB_API = "https://api.github.com"
_TIMEOUT = 30.0

# fetch_and_store は db.add / db.flush のみ行い、commit/rollback してはいけない。
# トランザクション境界は ensure_synced 側が握っており、失敗時の rollback は
# fetch_and_store が未コミットのまま積んだ変更を巻き戻すことに依存している。
FetchAndStore = Callable[["GitHubClient", Project, AsyncSession], Awaitable[None]]

# github_syncing=True のままプロセスが例外以外の形（SIGKILL/OOM等）で落ちた場合、
# フラグが残り続けて二度と再同期されなくなるのを防ぐための上限時間
STALE_SYNC_THRESHOLD = timedelta(minutes=10)


class GitHubClient:
    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, path: str, params: dict | None = None) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                res = await client.get(f"{GITHUB_API}{path}", params=params, headers=self._headers)
        except httpx.TimeoutException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub への接続がタイムアウトしました",
            ) from e
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub への接続に失敗しました",
            ) from e
        if res.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub APIの認証に失敗しました。再ログインしてください。",
            )
        if res.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub APIへのアクセスが拒否されました。レート制限に達している場合は、しばらくしてから再度お試しください。",
            )
        return res

    async def get_repo(self, owner: str, name: str) -> dict | None:
        res = await self._request(f"/repos/{owner}/{name}")
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    async def list_viewer_repos(self) -> list[dict]:
        """最大500件（5ページ）取得して返す。"""
        repos: list[dict] = []
        for page in range(1, 6):
            res = await self._request(
                "/user/repos",
                {"sort": "pushed", "affiliation": "owner,collaborator,organization_member", "per_page": 100, "page": page},
            )
            res.raise_for_status()
            page_items = res.json()
            repos.extend(page_items)
            if len(page_items) < 100:
                break
        return repos

    async def get_contributors(self, owner: str, name: str) -> list[dict]:
        res = await self._request(f"/repos/{owner}/{name}/contributors", {"per_page": 100})
        if res.status_code == 204:
            return []
        res.raise_for_status()
        return res.json()


def _is_fresh(project: Project, now: datetime, ttl: timedelta) -> bool:
    return project.github_synced_at is not None and now - project.github_synced_at < ttl


def _is_syncing(project: Project, now: datetime) -> bool:
    """死んだ同期（フラグが立ったまま STALE_SYNC_THRESHOLD 以上更新されていない）は
    syncing とみなさない。これにより、プロセスがcommit後に異常終了してもいつか復旧する。
    """
    if not project.github_syncing:
        return False
    started_at = project.github_syncing_started_at
    return started_at is not None and now - started_at < STALE_SYNC_THRESHOLD


async def ensure_synced(
    db: AsyncSession,
    project: Project,
    access_token: str,
    fetch_and_store: FetchAndStore,
    force: bool = False,
) -> Project:
    """GitHub APIへの実取得は数秒〜十数秒かかりうるため、その間はDBの行ロックを
    保持しない。同期中の他リクエストはフラグを見て待たずに今のキャッシュを返す
    （初回同期なら github_synced_at=None のまま）。完了を見せたい場合はフロント側で
    github_syncing をポーリングする想定（このIssueのスコープ外）。
    """
    now = datetime.now(timezone.utc)
    ttl = timedelta(seconds=settings.github_cache_ttl_seconds)

    if not force and _is_fresh(project, now, ttl):
        return project

    repo = ProjectRepository(db)
    locked = await repo.lock_for_sync(project.id)
    if locked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if _is_syncing(locked, now) or (not force and _is_fresh(locked, now, ttl)):
        # ロック待ちの間に他のリクエストが同期を完了させていた場合もここに来る
        await db.commit()
        return locked

    await repo.mark_syncing(locked, now)
    await db.commit()  # 即座にcommitしてロックを解放し、この後の外部API呼び出し中は保持しない

    try:
        await fetch_and_store(GitHubClient(access_token), locked, db)
        await repo.mark_synced(locked, datetime.now(timezone.utc))
        await db.commit()
    except Exception:
        await db.rollback()
        # mark_syncing は上で既にcommit済みのためrollbackでは戻らない。明示的に解除する
        reset = await repo.lock_for_sync(project.id)
        if reset is not None:
            await repo.clear_syncing(reset)
            await db.commit()
        raise

    return locked
