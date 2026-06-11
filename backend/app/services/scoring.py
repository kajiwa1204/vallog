import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.models import GitHubIssue, GitHubPullRequest, GitHubReview
from app.schemas.project import CategoryWeights
from app.schemas.score import (
    CategoryScores,
    GitHubItem,
    MemberScore,
    MetricRaw,
    TimelinePoint,
)

SP_LABEL_PATTERN = re.compile(r"^sp:?\s*(\d+)$", re.IGNORECASE)
BUG_LABEL_PATTERN = re.compile(r"bug", re.IGNORECASE)


def _is_bot(login: str) -> bool:
    return login.endswith("[bot]") or login == "unknown"


@dataclass
class _Raw:
    issues_opened: int = 0
    prs_opened: int = 0
    prs_merged: int = 0
    reviews_commented: int = 0
    approvals: int = 0
    changes_requested: int = 0
    review_tat_hours: list[float] = field(default_factory=list)
    sp_earned: int = 0
    sp_hours: float = 0.0
    bugs_assigned: int = 0
    prs_reopened: int = 0


def parse_sp(labels: list[str]) -> int | None:
    for label in labels:
        m = SP_LABEL_PATTERN.match(label.strip())
        if m:
            return int(m.group(1))
    return None


def collect_raw_metrics(
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
) -> dict[str, _Raw]:
    raw: dict[str, _Raw] = defaultdict(_Raw)
    pr_created_at = {p.number: p.gh_created_at for p in prs}

    for p in prs:
        if _is_bot(p.author_login):
            continue
        r = raw[p.author_login]
        r.prs_opened += 1
        if p.merged_at is not None:
            r.prs_merged += 1
        r.prs_reopened += p.reopened_count

    for i in issues:
        if not _is_bot(i.author_login):
            raw[i.author_login].issues_opened += 1
        is_bug = any(BUG_LABEL_PATTERN.search(label) for label in i.labels)
        sp = parse_sp(i.labels)
        for a in i.assignees:
            if _is_bot(a.login):
                continue
            if is_bug:
                raw[a.login].bugs_assigned += 1
            # タスク完了スピード: 獲得SP ÷ 経過時間（アサイン〜クローズ）
            if sp is not None and i.state == "closed" and i.closed_at is not None:
                start = a.assigned_at or i.gh_created_at
                hours = max(
                    (i.closed_at - start).total_seconds() / 3600, 0.1
                )
                r = raw[a.login]
                r.sp_earned += sp
                r.sp_hours += hours

    for rv in reviews:
        if _is_bot(rv.reviewer_login):
            continue
        r = raw[rv.reviewer_login]
        # コメント1件以上のレビューのみカウント
        if rv.body.strip():
            r.reviews_commented += 1
        if rv.state == "APPROVED":
            r.approvals += 1
        elif rv.state == "CHANGES_REQUESTED":
            r.changes_requested += 1
        created = pr_created_at.get(rv.pr_number)
        if created is not None and rv.submitted_at is not None:
            tat = (rv.submitted_at - created).total_seconds() / 3600
            if tat >= 0:
                r.review_tat_hours.append(tat)

    return dict(raw)


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """相対スコア = 個人の値 ÷ チーム全体の合計値"""
    total = sum(values.values())
    if total <= 0:
        return {k: 0.0 for k in values}
    return {k: v / total for k, v in values.items()}


def compute_scores(
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    weights: CategoryWeights,
    registered_users: dict[str, str | None],
) -> list[MemberScore]:
    raw = collect_raw_metrics(prs, issues, reviews)
    # 活動実績のないVallog登録メンバーもゼロスコアで表示する
    for login in registered_users:
        raw.setdefault(login, _Raw())
    members = list(raw.keys())
    if not members:
        return []

    # --- GitHub活動量: 4指標の均等割り ---
    opened = _normalize(
        {m: raw[m].issues_opened + raw[m].prs_opened for m in members}
    )
    review_contrib = _normalize({m: raw[m].reviews_commented for m in members})
    approve_rc = _normalize(
        {m: raw[m].approvals + raw[m].changes_requested for m in members}
    )
    # TATは短いほど貢献が大きいため、逆数（速さ）に変換して正規化する
    tat_speed = _normalize(
        {
            m: (
                1.0
                / max(
                    sum(raw[m].review_tat_hours) / len(raw[m].review_tat_hours),
                    0.1,
                )
                if raw[m].review_tat_hours
                else 0.0
            )
            for m in members
        }
    )
    activity = {
        m: (opened[m] + review_contrib[m] + approve_rc[m] + tat_speed[m]) / 4
        for m in members
    }

    # --- タスク完了スピード: 獲得SP ÷ 経過時間 ---
    speed = _normalize(
        {
            m: (raw[m].sp_earned / raw[m].sp_hours if raw[m].sp_hours > 0 else 0.0)
            for m in members
        }
    )

    # --- 品質・可用性: 手戻り（バグ報告 + PR再オープン）を差し引いた成果量 ---
    quality = _normalize(
        {
            m: max(
                raw[m].prs_merged - raw[m].bugs_assigned - raw[m].prs_reopened, 0
            )
            for m in members
        }
    )

    result = []
    for m in sorted(members):
        r = raw[m]
        avg_tat = (
            sum(r.review_tat_hours) / len(r.review_tat_hours)
            if r.review_tat_hours
            else None
        )
        total = (
            weights.activity * activity[m]
            + weights.speed * speed[m]
            + weights.quality * quality[m]
        ) / 100
        result.append(
            MemberScore(
                github_login=m,
                avatar_url=registered_users.get(m)
                or f"https://github.com/{m}.png",
                is_registered=m in registered_users,
                total=round(total, 4),
                categories=CategoryScores(
                    activity=round(activity[m], 4),
                    speed=round(speed[m], 4),
                    quality=round(quality[m], 4),
                ),
                metrics=MetricRaw(
                    issues_opened=r.issues_opened,
                    prs_opened=r.prs_opened,
                    prs_merged=r.prs_merged,
                    reviews_commented=r.reviews_commented,
                    approvals=r.approvals,
                    changes_requested=r.changes_requested,
                    avg_review_tat_hours=(
                        round(avg_tat, 1) if avg_tat is not None else None
                    ),
                    sp_earned=r.sp_earned,
                    sp_hours=round(r.sp_hours, 1),
                    sp_throughput=(
                        round(r.sp_earned / r.sp_hours, 4)
                        if r.sp_hours > 0
                        else None
                    ),
                    bugs_assigned=r.bugs_assigned,
                    prs_reopened=r.prs_reopened,
                ),
            )
        )
    result.sort(key=lambda s: s.total, reverse=True)
    return result


def build_timeline(
    login: str,
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    weeks: int = 12,
) -> list[TimelinePoint]:
    now = datetime.now(timezone.utc)
    start_of_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    buckets = [start_of_week - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]

    def bucket_index(ts: datetime) -> int | None:
        for idx in range(len(buckets) - 1, -1, -1):
            if ts >= buckets[idx]:
                return idx
        return None

    counts = {b: {"prs": 0, "issues": 0, "reviews": 0} for b in buckets}
    for p in prs:
        if p.author_login == login and (idx := bucket_index(p.gh_created_at)) is not None:
            counts[buckets[idx]]["prs"] += 1
    for i in issues:
        if i.author_login == login and (idx := bucket_index(i.gh_created_at)) is not None:
            counts[buckets[idx]]["issues"] += 1
    for rv in reviews:
        if (
            rv.reviewer_login == login
            and rv.submitted_at is not None
            and (idx := bucket_index(rv.submitted_at)) is not None
        ):
            counts[buckets[idx]]["reviews"] += 1

    return [
        TimelinePoint(week_start=b, **counts[b]) for b in buckets
    ]


def recent_items_for_member(
    login: str,
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    limit: int = 10,
) -> tuple[list[GitHubItem], list[GitHubItem], list[GitHubItem]]:
    pr_map = {p.number: p for p in prs}
    recent_prs = [
        GitHubItem(
            number=p.number,
            title=p.title,
            state="merged" if p.merged_at else p.state,
            html_url=p.html_url,
            created_at=p.gh_created_at,
        )
        for p in prs
        if p.author_login == login
    ][:limit]
    recent_issues = [
        GitHubItem(
            number=i.number,
            title=i.title,
            state=i.state,
            html_url=i.html_url,
            created_at=i.gh_created_at,
            extra=f"SP:{sp}" if (sp := parse_sp(i.labels)) is not None else None,
        )
        for i in issues
        if i.author_login == login or any(a.login == login for a in i.assignees)
    ][:limit]
    recent_reviews = [
        GitHubItem(
            number=rv.pr_number,
            title=(
                pr_map[rv.pr_number].title if rv.pr_number in pr_map else f"PR #{rv.pr_number}"
            ),
            state=rv.state.lower(),
            html_url=rv.html_url,
            created_at=rv.submitted_at,
        )
        for rv in reviews
        if rv.reviewer_login == login and rv.submitted_at is not None
    ][:limit]
    return recent_prs, recent_issues, recent_reviews
