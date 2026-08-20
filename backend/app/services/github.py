import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import httpx

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.models.project import Project
from app.repositories.github_cache import (
    AssigneeData,
    GitHubCacheRepository,
    IssueData,
    PullRequestData,
    ReviewData,
)
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

# 1回の同期で取得する上限ページ数・PR数。レート制限（5,000 req/h）の予算内に収める。
#
# MAX_LIST_PAGES=5（× per_page=100）で PR・Issue は各500件が上限になる。これはレート制限
# だけの都合ではなく、**貢献評価の周期が四半期であること**を前提にした設計判断。1四半期に
# 500件を超えるPRが動くチームは想定しておらず、企業に導入する場合でも直近500件あれば1Qの
# 評価は成立する、という見立てで置いている。
#
# したがって古い履歴がキャッシュに載らないのは仕様であり、欠陥ではない。上限を上げる必要が
# 出るのは「評価対象期間の変化がこの件数を超える」ときに限られ、そのときは件数ではなく
# 期間（updated_at ベースの差分同期）で切る設計に変えるべき。
MAX_LIST_PAGES = 5
MAX_EVENT_PAGES = 10
MAX_REVIEW_TARGETS = 100
REVIEW_CONCURRENCY = 5

_SP_LABEL_RE = re.compile(r"^SP:(\d+)$", re.IGNORECASE)

logger = logging.getLogger(__name__)

# GitHubのBotは通常 ``[bot]`` 接尾辞を持つが、Copilotのcontributors応答は
# login="Copilot", type="Bot" になる。キャッシュ済み活動にはtypeを保存していないため、
# 接尾辞なしで現れる既知のBotだけloginでも判定できるようにする。
_KNOWN_BOT_LOGINS = frozenset({"copilot"})

NOT_DONE_STATE_REASONS = frozenset({"not_planned", "duplicate"})
"""成果として数えないGitHub Issueのクローズ理由。

GitHubのクローズUIでは completed が既定なので、それだけでは明確な完了意思を判定できない。
一方、not_planned と duplicate は明示的に選ばれる値で、成果として数えない。GitHub由来の
状態値に関する知識として、変化ログとスコア計算で共有する。
"""


def is_excluded_github_actor(login: str, actor_type: str | None = None) -> bool:
    """貢献者・スコア・変化ログから除外するGitHub上の実行者か。"""
    normalized_login = login.casefold()
    normalized_type = actor_type.casefold() if actor_type is not None else None
    return (
        normalized_login == "unknown"
        or normalized_login.endswith("[bot]")
        or normalized_login in _KNOWN_BOT_LOGINS
        or normalized_type == "bot"
    )


class GitHubClient:
    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        # 呼び出しごとに接続を張り直さないよう、インスタンスの生存期間で共有する
        self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        self._granted_scopes: set[str] | None = None

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._client.aclose()

    async def _request(
        self,
        path: str,
        params: dict | None = None,
        *,
        not_found_ok: bool = False,
        accept: str | None = None,
    ) -> httpx.Response:
        headers = self._headers if accept is None else {**self._headers, "Accept": accept}
        try:
            res = await self._client.get(f"{GITHUB_API}{path}", params=params, headers=headers)
        except httpx.TimeoutException as e:
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                ErrorCode.GITHUB_TIMEOUT,
                "Connection to GitHub timed out",
            ) from e
        except httpx.HTTPError as e:
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                ErrorCode.GITHUB_UNAVAILABLE,
                "Failed to connect to GitHub",
            ) from e
        raw_scopes = res.headers.get("X-OAuth-Scopes")
        if raw_scopes is not None:
            self._granted_scopes = {s.strip() for s in raw_scopes.split(",") if s.strip()}
        if res.status_code == 401:
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                ErrorCode.GITHUB_AUTH_FAILED,
                "GitHub API authentication failed",
            )
        if res.status_code == 403:
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                ErrorCode.GITHUB_FORBIDDEN,
                "GitHub API access denied (possibly rate limited)",
            )
        if res.status_code == 404 and not_found_ok:
            return res
        if res.status_code == 404:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                ErrorCode.REPO_NOT_FOUND,
                "GitHub repository or resource not found",
            )
        if res.status_code == 429:
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                ErrorCode.GITHUB_RATE_LIMITED,
                "GitHub API rate limit exceeded",
            )
        if res.status_code >= 500:
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                ErrorCode.GITHUB_UNAVAILABLE,
                "GitHub API returned a server error",
            )
        if res.status_code >= 400:
            # 401/403/404/429/5xxで拾いきれない想定外の4xx（410/422等）。生のhttpx例外を
            # routerまで漏らさず、契約通りAppError/GITHUB_*として返す
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                ErrorCode.GITHUB_UNAVAILABLE,
                f"GitHub API returned an unexpected status: {res.status_code}",
            )
        return res

    async def get_repo(self, owner: str, name: str) -> dict | None:
        res = await self._request(f"/repos/{owner}/{name}", not_found_ok=True)
        if res.status_code == 404:
            return None
        return res.json()

    async def _paginated_with_meta(
        self, path: str, params: dict, max_pages: int, per_page: int = 100
    ) -> tuple[list[dict], bool]:
        """page=1..max_pages を順に取得し、1ページの件数が per_page 未満になったら打ち切る。

        (取得結果, max_pagesで打ち切ったか) を返す。
        """
        results: list[dict] = []
        truncated = True
        for page in range(1, max_pages + 1):
            res = await self._request(path, {**params, "per_page": per_page, "page": page})
            batch = res.json()
            results.extend(batch)
            if len(batch) < per_page:
                truncated = False
                break
        else:
            # max_pagesに達して打ち切った＝取得しきれていないデータがある可能性
            logger.warning(
                "github pagination capped: path=%s max_pages=%d params=%r (more data may exist)",
                path,
                max_pages,
                params,
            )
        return results, truncated

    async def _paginated(
        self, path: str, params: dict, max_pages: int, per_page: int = 100
    ) -> list[dict]:
        results, _ = await self._paginated_with_meta(path, params, max_pages, per_page)
        return results

    async def list_viewer_repos(self) -> tuple[list[dict], bool]:
        """最大500件（5ページ）取得し、(リポジトリ, 打ち切ったか) を返す。"""
        return await self._paginated_with_meta(
            "/user/repos",
            {"sort": "pushed", "affiliation": "owner,collaborator,organization_member"},
            max_pages=5,
        )

    @property
    def granted_scopes(self) -> set[str] | None:
        """直近のレスポンスの `X-OAuth-Scopes` から得たスコープ。判定不能なら None。

        スコープを増やしても既存トークンには反映されないため、再認可が必要かどうかの
        判定に使う。ヘッダは全レスポンスに付くので、専用のリクエストは投げない。

        None になるのは「まだ1度もリクエストしていない」か「トークンがヘッダを返さない」
        場合。後者は GitHub App のユーザートークンが該当する（Classic OAuth トークン
        固有のヘッダのため）。空集合（＝スコープ皆無）と区別できないと、GitHub App へ
        移行した際に再認可導線が出っぱなしになるので、両者を分けている。
        """
        return self._granted_scopes

    async def get_contributors(self, owner: str, name: str) -> list[dict]:
        res = await self._request(f"/repos/{owner}/{name}/contributors", {"per_page": 100})
        if res.status_code == 204:
            return []
        return res.json()

    async def list_pull_requests(self, owner: str, name: str) -> list[dict]:
        return await self._paginated(
            f"/repos/{owner}/{name}/pulls",
            {"state": "all", "sort": "created", "direction": "desc"},
            MAX_LIST_PAGES,
        )

    async def list_issues(self, owner: str, name: str) -> list[dict]:
        """Issue一覧にはPRも含まれる（GitHub仕様）。呼び出し側で pull_request キーの有無により除外する。"""
        return await self._paginated(
            f"/repos/{owner}/{name}/issues",
            {"state": "all", "sort": "created", "direction": "desc"},
            MAX_LIST_PAGES,
        )

    async def list_issue_events(self, owner: str, name: str) -> list[dict]:
        return await self._paginated(f"/repos/{owner}/{name}/issues/events", {}, MAX_EVENT_PAGES)

    async def list_review_comments(self, owner: str, name: str) -> list[dict]:
        """レビューごとのコメント件数集計用。pull_request_review_id でグルーピングする。
        上限到達時に直近のコメントを優先して残すため、他の一覧系と同じく作成日時降順で取得する。
        """
        return await self._paginated(
            f"/repos/{owner}/{name}/pulls/comments",
            {"sort": "created", "direction": "desc"},
            MAX_LIST_PAGES,
        )

    async def fetch_pr_diff(self, owner: str, name: str, number: int) -> str:
        """PRのdiff本文を取得する（PRサマリー生成の入力用）。"""
        res = await self._request(
            f"/repos/{owner}/{name}/pulls/{number}",
            accept="application/vnd.github.diff",
        )
        return res.text

    async def list_reviews_for_prs(
        self, owner: str, name: str, numbers: list[int]
    ) -> dict[int, list[dict]]:
        semaphore = asyncio.Semaphore(REVIEW_CONCURRENCY)

        async def fetch(number: int) -> tuple[int, list[dict]]:
            async with semaphore:
                res = await self._request(
                    f"/repos/{owner}/{name}/pulls/{number}/reviews", {"per_page": 100}
                )
                return number, res.json()

        results = await asyncio.gather(*(fetch(n) for n in numbers))
        return dict(results)


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
        async with GitHubClient(access_token) as client:
            await fetch_and_store(client, locked, db)
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


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_dt_required(value: str) -> datetime:
    """gh_created_at相当の必須フィールド用。GitHub APIは常に値を返す前提のフィールドに使う。
    _parse_dtはOptionalフィールド専用（merged_at/closed_at/submitted_at等）で、
    必須フィールドに使うとNoneが型チェックをすり抜けてDTOに渡り、DBのNOT NULL制約違反という
    離れた場所で初めて失敗が顕在化してしまう。
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _actor_login(actor: dict | None, context: str) -> str:
    """user/assignee/reviewerフィールドからloginを取り出す。GitHubアカウント削除等でNoneに
    なるのは正常だが、パース側のバグ（フィールド名変更等）による欠落と区別できないため、
    フォールバックが発生したことをログに残す。
    """
    login = (actor or {}).get("login")
    if login is None:
        logger.warning("github %s: actor login missing, falling back to 'unknown': %r", context, actor)
        return "unknown"
    return login


def _parse_story_points(labels: list[str]) -> int | None:
    for label in labels:
        m = _SP_LABEL_RE.match(label)
        if m:
            return int(m.group(1))
    return None


def _aggregate_issue_events(
    events: list[dict], pr_numbers: set[int]
) -> tuple[dict[tuple[int, str], datetime], dict[int, int]]:
    """assigned/reopenedイベントから、アサイン日時（複数回アサインされた場合は最初の時刻）と
    PRの再オープン回数（品質・可用性カテゴリの「手戻り率」指標。docs/scoring_design.md が
    定義するのは「PR再オープン回数」であり、issueのreopenedはスコープ外のため pr_numbers で
    絞り込む）を集計する。
    """
    assigned_at: dict[tuple[int, str], datetime] = {}
    reopened_count: dict[int, int] = {}
    for ev in events:
        issue = ev.get("issue") or {}
        number = issue.get("number")
        if number is None:
            continue
        event_type = ev.get("event")
        if event_type == "assigned" and ev.get("assignee"):
            key = (number, _actor_login(ev.get("assignee"), "issue_event.assignee"))
            ts = _parse_dt(ev.get("created_at"))
            if ts is not None and (key not in assigned_at or ts < assigned_at[key]):
                assigned_at[key] = ts
        elif event_type == "reopened" and number in pr_numbers:
            reopened_count[number] = reopened_count.get(number, 0) + 1
    return assigned_at, reopened_count


def _count_comments_by_review(comments: list[dict]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for c in comments:
        review_id = c.get("pull_request_review_id")
        if review_id is None:
            continue
        counts[review_id] = counts.get(review_id, 0) + 1
    return counts


def _build_pull_request_rows(
    pulls: list[dict], reopened_count: dict[int, int]
) -> list[PullRequestData]:
    return [
        PullRequestData(
            github_id=p["id"],
            number=p["number"],
            title=p["title"],
            body=p.get("body"),
            head_sha=(p.get("head") or {}).get("sha"),
            author_login=_actor_login(p.get("user"), "pull_request.user"),
            state=p["state"],
            draft=bool(p.get("draft")),
            html_url=p["html_url"],
            gh_created_at=_parse_dt_required(p["created_at"]),
            merged_at=_parse_dt(p.get("merged_at")),
            closed_at=_parse_dt(p.get("closed_at")),
            reopened_count=reopened_count.get(p["number"], 0),
        )
        for p in pulls
    ]


def _build_issue_rows(
    issues: list[dict], assigned_at: dict[tuple[int, str], datetime]
) -> list[IssueData]:
    rows = []
    for i in issues:
        if "pull_request" in i:
            continue  # /issues エンドポイントにはPRも含まれるため除外
        number = i["number"]
        labels = [label["name"] for label in i.get("labels", [])]
        assignee_logins = [_actor_login(a, "issue.assignees") for a in i.get("assignees", [])]
        rows.append(
            IssueData(
                github_id=i["id"],
                number=number,
                title=i["title"],
                author_login=_actor_login(i.get("user"), "issue.user"),
                state=i["state"],
                state_reason=i.get("state_reason"),
                labels=labels,
                story_points=_parse_story_points(labels),
                html_url=i["html_url"],
                gh_created_at=_parse_dt_required(i["created_at"]),
                closed_at=_parse_dt(i.get("closed_at")),
                assignees=[
                    AssigneeData(login=login, assigned_at=assigned_at.get((number, login)))
                    for login in assignee_logins
                ],
            )
        )
    return rows


def _build_review_rows(
    reviews_by_pr: dict[int, list[dict]], comment_counts: dict[int, int]
) -> list[ReviewData]:
    return [
        ReviewData(
            github_id=r["id"],
            pr_number=pr_number,
            reviewer_login=_actor_login(r.get("user"), "review.user"),
            state=r["state"],
            body=r.get("body") or "",
            comment_count=comment_counts.get(r["id"], 0),
            html_url=r["html_url"],
            submitted_at=_parse_dt(r.get("submitted_at")),
        )
        for pr_number, reviews in reviews_by_pr.items()
        for r in reviews
    ]


async def fetch_and_store(client: GitHubClient, project: Project, db: AsyncSession) -> None:
    """`ensure_synced` に渡す `FetchAndStore` の実装。GitHub APIからPR・Issue・Reviewを取得し、
    `GitHubCacheRepository` 経由でDBにupsertする。db.commit/rollbackはしない（ensure_synced側の責務）。
    """
    owner, name = project.repo_owner, project.repo_name
    pulls, issues, events, review_comments = await asyncio.gather(
        client.list_pull_requests(owner, name),
        client.list_issues(owner, name),
        client.list_issue_events(owner, name),
        client.list_review_comments(owner, name),
    )
    pr_numbers = {p["number"] for p in pulls}
    assigned_at, reopened_count = _aggregate_issue_events(events, pr_numbers)
    comment_counts = _count_comments_by_review(review_comments)

    review_targets = [p["number"] for p in pulls[:MAX_REVIEW_TARGETS]]
    reviews_by_pr = await client.list_reviews_for_prs(owner, name, review_targets)

    cache_repo = GitHubCacheRepository(db)
    await cache_repo.upsert_pull_requests(project.id, _build_pull_request_rows(pulls, reopened_count))
    await cache_repo.upsert_issues(project.id, _build_issue_rows(issues, assigned_at))
    await cache_repo.upsert_reviews(project.id, _build_review_rows(reviews_by_pr, comment_counts))
