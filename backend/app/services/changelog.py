"""変化ログ（第1層・AIなし）を組み立てる。

「いまチームが何を動かしているか」を、キャッシュ済みGitHubデータ（PR・Issue・Review）の
読み取りだけで時系列に並べる。スコア・順位は出さない（docs/scoring_design.md
「Goodhart対策とスコアの事後開示」）。スコアの開示は振り返り（画面7）が担い、ここは
「何が起きたか」の事実だけを一次リンク付きで映す静か側を担当する。

各エントリはGitHubオブジェクト単位（PR1件・Issue1件・レビュー1件で1行）。
「作成」と「マージ」を別行に割らないのは、一覧の主目的が
「いま何が動いているか」の把握であり、同じPRが複数行に散ると読み取りづらくなるため。
時刻は最新の状態変化（PRならマージ＞クローズ＞作成）を採る。

このモジュールはDBに書き込まず、新規テーブルも持たない。
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_cache import GitHubIssue, GitHubPullRequest, GitHubReview
from app.models.project import Project
from app.repositories.github_cache import GitHubCacheRepository
from app.schemas.changelog import ChangeLogEntry, ChangeLogNotes, ChangeLogResponse
from app.services.github import ensure_synced, fetch_and_store

DEFAULT_LIMIT = 50


def is_excluded_login(login: str) -> bool:
    """変化ログに載せない実行者か。

    "unknown" は services/github.py の _actor_login が login を取得できなかったときの
    フォールバック値で、実在の貢献者ではない。botのPR（依存更新等）はチームの動きとして
    読む価値が薄いため除く。services/scoring.py の _is_excluded と同じ方針。
    """
    return login.endswith("[bot]") or login == "unknown"


def _reviews_by_pr(reviews: list[GitHubReview]) -> dict[int, list[GitHubReview]]:
    by_pr: dict[int, list[GitHubReview]] = {}
    for r in reviews:
        by_pr.setdefault(r.pr_number, []).append(r)
    return by_pr


def _first_external_review(
    pr: GitHubPullRequest, reviews: list[GitHubReview]
) -> GitHubReview | None:
    """PR作者以外による最初のレビュー。

    PR作者が自分のPRにインラインコメントを付けるとGitHubは作者名義のCOMMENTEDレビューを
    作る。これを「レビューされた」と数えるとセルフコメントだけでレビュー済みに見えてしまう
    ため除外する（services/scoring.py の _is_self_review と同じ理由）。
    """
    external = [
        r
        for r in reviews
        if r.reviewer_login != pr.author_login and r.submitted_at is not None
    ]
    if not external:
        return None
    return min(external, key=lambda r: r.submitted_at)


def _elapsed_hours(start: datetime, end: datetime) -> float | None:
    """startからendまでの時間。逆転していればNone（時刻の不整合を数値として出さない）。"""
    hours = (end - start).total_seconds() / 3600
    return round(hours, 1) if hours >= 0 else None


def _pr_entry(pr: GitHubPullRequest, reviews: list[GitHubReview]) -> ChangeLogEntry:
    first_review = _first_external_review(pr, reviews)
    return ChangeLogEntry(
        kind="pull_request",
        number=pr.number,
        title=pr.title,
        actor_login=pr.author_login,
        state="merged" if pr.merged_at is not None else pr.state,
        occurred_at=pr.merged_at or pr.closed_at or pr.gh_created_at,
        html_url=pr.html_url,
        notes=ChangeLogNotes(
            turnaround_hours=(
                _elapsed_hours(pr.gh_created_at, first_review.submitted_at)
                if first_review is not None
                else None
            ),
            reviewed_by_others=first_review is not None,
            reopened_count=pr.reopened_count,
            draft=pr.draft,
        ),
    )


def _issue_entry(issue: GitHubIssue) -> ChangeLogEntry:
    return ChangeLogEntry(
        kind="issue",
        number=issue.number,
        title=issue.title,
        actor_login=issue.author_login,
        state=issue.state,
        occurred_at=issue.closed_at or issue.gh_created_at,
        html_url=issue.html_url,
        notes=ChangeLogNotes(story_points=issue.story_points),
    )


def _review_entry(review: GitHubReview, pr: GitHubPullRequest) -> ChangeLogEntry:
    return ChangeLogEntry(
        kind="review",
        number=review.pr_number,
        title=pr.title,
        actor_login=review.reviewer_login,
        state=review.state.lower(),
        occurred_at=review.submitted_at,
        html_url=review.html_url,
        notes=ChangeLogNotes(
            turnaround_hours=_elapsed_hours(pr.gh_created_at, review.submitted_at)
        ),
    )


def _issue_logins(issue: GitHubIssue) -> set[str]:
    """そのIssueを「動かしている」人。起票者と担当者の両方を含める。"""
    return {issue.author_login} | {a.login for a in issue.assignees}


def build_changelog(
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    member: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> ChangeLogResponse:
    """キャッシュ済みGitHubデータを時系列の変化ログにまとめる（純粋関数・DBアクセスなし）。

    member を渡すとそのメンバーの変化だけに絞る（画面5・画面7で再利用）。
    絞り込みは「本人がPRを出した / Issueを起票または担当した / レビューを出した」を対象とする。
    """
    pr_by_number = {pr.number: pr for pr in prs}
    reviews_by_pr = _reviews_by_pr(reviews)

    entries: list[ChangeLogEntry] = []

    for pr in prs:
        if is_excluded_login(pr.author_login):
            continue
        if member is not None and pr.author_login != member:
            continue
        entries.append(_pr_entry(pr, reviews_by_pr.get(pr.number, [])))

    for issue in issues:
        if is_excluded_login(issue.author_login):
            continue
        if member is not None and member not in _issue_logins(issue):
            continue
        entries.append(_issue_entry(issue))

    for review in reviews:
        if review.submitted_at is None:
            continue
        if is_excluded_login(review.reviewer_login):
            continue
        if member is not None and review.reviewer_login != member:
            continue
        pr = pr_by_number.get(review.pr_number)
        # レビュー対象PRがキャッシュの取得上限から溢れていると引けない。タイトルも
        # 一次リンクの文脈も出せないため、その1件だけ落とす
        if pr is None:
            continue
        if review.reviewer_login == pr.author_login:
            continue
        entries.append(_review_entry(review, pr))

    entries.sort(key=lambda e: e.occurred_at, reverse=True)
    return ChangeLogResponse(entries=entries[:limit])


async def get_changelog(
    db: AsyncSession,
    project: Project,
    access_token: str,
    member: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> ChangeLogResponse:
    """TTLに従いGitHubキャッシュを最新化してから変化ログを組み立てる。"""
    await ensure_synced(db, project, access_token, fetch_and_store)

    cache = GitHubCacheRepository(db)
    prs = await cache.list_pull_requests(project.id)
    issues = await cache.list_issues(project.id)
    reviews = await cache.list_reviews(project.id)
    return build_changelog(prs, issues, reviews, member=member, limit=limit)
