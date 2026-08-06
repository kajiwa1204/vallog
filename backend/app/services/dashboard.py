"""チーム状況パネル4種（第1層・AIなし）を組み立てる。

ダッシュボード（画面4）にスコアは載せない（docs/scoring_design.md
「Goodhart対策とスコアの事後開示」。スコアの開示は分配画面が担う）。代わりにこのモジュールが
「チームがいま何を動かしているか」を4通りに畳んで返す。4種はいずれも重み付けも順位付けも
しない事実の集計で、報酬に接続されていない（①ターゲットが折れている）。

pulse は services/changelog.py の build_changelog がまとめたエントリをそのまま日付で
畳んだもの。同じ画面に日次バーと変化ログの一覧が並ぶため、独自に時刻を採り直すと
「バーは8/4に3件と言っているのに一覧にその日の行がない」という読めない画面になる。
除外規則（bot・unknown・対象PRを引けないレビュー）も自動的に一致する。

このモジュールはDBに書き込まず、新規テーブルも持たない。既存キャッシュの読み取りだけ。
"""

import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_cache import GitHubIssue, GitHubPullRequest, GitHubReview
from app.models.project import Project
from app.repositories.github_cache import GitHubCacheRepository
from app.schemas.changelog import ChangeLogEntry
from app.schemas.dashboard import (
    Attention,
    AttentionIssue,
    AttentionPullRequest,
    DashboardResponse,
    PulseDay,
    ReviewEdge,
    Theme,
)
from app.services.changelog import build_changelog, is_excluded_login
from app.services.github import ensure_synced, fetch_and_store

DEFAULT_PULSE_DAYS = 14
STALLED_ISSUE_DAYS = 7

# SPラベルは「動いている領域」ではなくストーリーポイントなので themes から落とす。
# services/github.py の _SP_LABEL_RE と同じパターン（あちらは別Issueで編集中のため
# import せず持つ。集約は #95 の unknown センチネル統合と合わせて行う）
_SP_LABEL_RE = re.compile(r"^SP:(\d+)$", re.IGNORECASE)


def _local_date(moment: datetime, tz_offset_minutes: int) -> date:
    """UTCの時刻を、閲覧者のローカル日付に畳む。

    UTCのまま日付を採ると境界が 09:00 JST になり、00:00〜09:00 JST の活動が前日の
    バーに入る。夜に動くチームでは「朝9時まで今日が空」になって体感と外れるため、
    フロントから受けたオフセットで補正する。
    """
    return (moment + timedelta(minutes=tz_offset_minutes)).date()


def _hours_since(start: datetime, now: datetime) -> float:
    """startから現在までの時間。

    changelog の _elapsed_hours と違い None を返さない。あちらは「レビューが付くまで」の
    ように区間が成立しないことがありうるが、こちらは「まだ止まっている時間」で、
    未来の作成時刻（時計のずれ）は0時間として扱えば足りる。
    """
    return round(max((now - start).total_seconds() / 3600, 0.0), 1)


def _pulse(
    entries: list[ChangeLogEntry], now: datetime, days: int, tz_offset_minutes: int
) -> list[PulseDay]:
    today = _local_date(now, tz_offset_minutes)
    start = today - timedelta(days=days - 1)

    counts: dict[date, dict[str, int]] = {
        start + timedelta(days=i): {"pull_request": 0, "issue": 0, "review": 0}
        for i in range(days)
    }

    for entry in entries:
        bucket = counts.get(_local_date(entry.occurred_at, tz_offset_minutes))
        if bucket is None:
            continue
        bucket[entry.kind] += 1

    return [
        PulseDay(
            date=day,
            pull_requests=bucket["pull_request"],
            issues=bucket["issue"],
            reviews=bucket["review"],
        )
        for day, bucket in sorted(counts.items())
    ]


def _attention_pr(entry: ChangeLogEntry, now: datetime) -> AttentionPullRequest:
    # OPEN PRのエントリでは occurred_at が作成時刻そのもの（マージもクローズもされて
    # いないため）。changelog の時刻採用規則に乗っているので別途 gh_created_at を
    # 引き直す必要がない
    return AttentionPullRequest(
        number=entry.number,
        title=entry.title,
        author_login=entry.actor_login,
        html_url=entry.html_url,
        opened_at=entry.occurred_at,
        waiting_hours=_hours_since(entry.occurred_at, now),
        draft=bool(entry.notes.draft),
    )


def _attention(
    entries: list[ChangeLogEntry], issues: list[GitHubIssue], now: datetime
) -> Attention:
    """止まっているものを集める。

    PR側を変化ログのエントリから作るのは、「他者レビューがない」の判定を1箇所に保つため。
    同じ述語を書き直すと、変化ログが「他者レビューなし」と注記しているPRがこのパネルに
    出てこない、という食い違いが起きうる。
    """
    review_wanted: list[AttentionPullRequest] = []
    drafts: list[AttentionPullRequest] = []

    for entry in entries:
        if entry.kind != "pull_request" or entry.state != "open":
            continue
        if entry.notes.draft:
            drafts.append(_attention_pr(entry, now))
        elif entry.notes.reviewed_by_others is False:
            review_wanted.append(_attention_pr(entry, now))

    stalled_threshold = now - timedelta(days=STALLED_ISSUE_DAYS)
    stalled: list[AttentionIssue] = []
    for issue in issues:
        if issue.state != "open":
            continue
        for assignee in issue.assignees:
            # 除外はassigneeにだけかける。botが起票したIssueでも、人間が担当して
            # 止まっているなら気にかける対象であることに変わりはない
            if assignee.assigned_at is None or is_excluded_login(assignee.login):
                continue
            if assignee.assigned_at > stalled_threshold:
                continue
            stalled.append(
                AttentionIssue(
                    number=issue.number,
                    title=issue.title,
                    html_url=issue.html_url,
                    assignee_login=assignee.login,
                    assigned_at=assignee.assigned_at,
                    stalled_hours=_hours_since(assignee.assigned_at, now),
                )
            )

    review_wanted.sort(key=lambda p: p.waiting_hours, reverse=True)
    drafts.sort(key=lambda p: p.waiting_hours, reverse=True)
    stalled.sort(key=lambda i: i.stalled_hours, reverse=True)
    return Attention(review_wanted=review_wanted, drafts=drafts, stalled_issues=stalled)


def _collaboration(
    prs: list[GitHubPullRequest], reviews: list[GitHubReview]
) -> list[ReviewEdge]:
    """レビュアー → PR作者 の本数。

    変化ログと違い、作者がbotのPRへのレビューは数えない。あちらは「レビューという
    実労働を分配の根拠から消さない」ために残すが、こちらが答えるのは「誰が誰の仕事を
    見ているか」で、依存更新PRへのレビューをそこに混ぜると人同士の流れが読めなくなる。
    """
    author_by_number = {pr.number: pr.author_login for pr in prs}

    counts: dict[tuple[str, str], int] = defaultdict(int)
    for review in reviews:
        if review.submitted_at is None or is_excluded_login(review.reviewer_login):
            continue
        author = author_by_number.get(review.pr_number)
        if author is None or is_excluded_login(author):
            continue
        if author == review.reviewer_login:
            continue
        counts[(review.reviewer_login, author)] += 1

    edges = [
        ReviewEdge(reviewer_login=reviewer, author_login=author, count=count)
        for (reviewer, author), count in counts.items()
    ]
    # 同数のときに並びが実行ごとに変わらないよう、ログイン名まで見て決める
    edges.sort(key=lambda e: (-e.count, e.reviewer_login, e.author_login))
    return edges


def _themes(issues: list[GitHubIssue]) -> list[Theme]:
    open_counts: dict[str, int] = defaultdict(int)
    closed_counts: dict[str, int] = defaultdict(int)

    for issue in issues:
        if is_excluded_login(issue.author_login):
            continue
        for label in issue.labels:
            if _SP_LABEL_RE.match(label):
                continue
            # not_planned（却下・重複）もクローズ側に数える。領域として動いていない
            # ことに変わりはなく、ここでの関心は完了/未完了ではなく open/その他
            if issue.state == "open":
                open_counts[label] += 1
            else:
                closed_counts[label] += 1

    themes = [
        Theme(
            label=label,
            open_count=open_counts.get(label, 0),
            closed_count=closed_counts.get(label, 0),
        )
        for label in set(open_counts) | set(closed_counts)
    ]
    themes.sort(key=lambda t: (-(t.open_count + t.closed_count), t.label))
    return themes


def build_dashboard(
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    now: datetime,
    days: int = DEFAULT_PULSE_DAYS,
    tz_offset_minutes: int = 0,
    synced_at: datetime | None = None,
) -> DashboardResponse:
    """キャッシュ済みGitHubデータをチーム状況パネル4種にまとめる（純粋関数・DBアクセスなし）。

    now を引数で受けるのは「レビュー待ち何時間」「担当から何日」が現在時刻に依存するため。
    datetime.now() を内側で呼ぶとテストが時計に依存する。
    """
    # limit にエントリ数の上限（3種の合計）を渡して打ち切りを起こさせない。pulse は
    # 期間内の全件を数える必要があり、changelog の既定50件では足りない
    changelog = build_changelog(
        prs, issues, reviews, limit=len(prs) + len(issues) + len(reviews)
    )

    return DashboardResponse(
        synced_at=synced_at,
        pulse=_pulse(changelog.entries, now, days, tz_offset_minutes),
        attention=_attention(changelog.entries, issues, now),
        collaboration=_collaboration(prs, reviews),
        themes=_themes(issues),
    )


async def get_dashboard(
    db: AsyncSession,
    project: Project,
    access_token: str,
    days: int = DEFAULT_PULSE_DAYS,
    tz_offset_minutes: int = 0,
) -> DashboardResponse:
    """TTLに従いGitHubキャッシュを最新化してからパネル4種を組み立てる。"""
    # 戻り値の project を使う。同期を挟んだ場合、引数の project は github_synced_at が
    # 古いままで、レスポンスが「まだ一度も同期していない」と嘘をつく
    project = await ensure_synced(db, project, access_token, fetch_and_store)

    cache = GitHubCacheRepository(db)
    prs = await cache.list_pull_requests(project.id)
    issues = await cache.list_issues(project.id)
    reviews = await cache.list_reviews(project.id)
    return build_dashboard(
        prs,
        issues,
        reviews,
        now=datetime.now(timezone.utc),
        days=days,
        tz_offset_minutes=tz_offset_minutes,
        synced_at=project.github_synced_at,
    )
