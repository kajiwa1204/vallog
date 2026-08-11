"""チーム状況パネル4種（第1層・AIなし）を組み立てる。

ダッシュボード（画面4）にスコアは載せない（docs/scoring_design.md
「Goodhart対策とスコアの事後開示」。スコアの開示は分配画面が担う）。代わりにこのモジュールが
「チームがいま何を動かしているか」を4通りに畳んで返す。4種はいずれも重み付けをせず、
報酬の算定式には現れない。

ただし attention の停滞時間は、Issueがクローズされた時点でスピードカテゴリの経過時間
（services/scoring.py の _speed_values。起点は同じ assigned_at）に連続する。それを承知で
残すのは、止まっているものを動かすには持ち主と経過が要るためで、行動可能性を優先した
判断である。一方、レビュー本数のように「安く積める量」を個人別に集約して序列化するパネルは
置かない（変化ログが意図的に脱集約している情報を、画面が再集約し直すことになるため）。

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
    ChangesRequestedPullRequest,
    DashboardResponse,
    DoneItem,
    PulseDay,
    Theme,
)
from app.services.changelog import build_changelog, is_excluded_login
from app.services.github import ensure_synced, fetch_and_store

DEFAULT_PULSE_DAYS = 14
STALLED_ISSUE_DAYS = 7
# 「片づいたもの」に出す件数。詰まりが無いチームでも画面が空にならない程度で、
# 変化ログ（主役）と読み比べる量にはしない
RECENTLY_DONE_LIMIT = 6
# 最終レビューの判定に使う状態。
# COMMENTED は承認状態を表明していないので含めない。
# DISMISSED を含めないのは「覆さないから」ではなく逆で、dismiss は判断の取り消しそのもの。
# GitHubは dismiss しても新しいレビューを作らず、元のレビュー行の state を
# CHANGES_REQUESTED から DISMISSED に書き換える。したがってここから外しておけば、
# そのPRは latest に載らなくなり修正待ちから正しく消える。
# 「DISMISSED も決定的だから含めよう」と足すと、取り消し済みの指摘で止まったままになる
_DECISIVE_REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED"}
# レビュー待ちとして挙げるまでの猶予。開いた直後のPRは「気にかけること」ではないため、
# 停滞Issue（STALLED_ISSUE_DAYS）と同じく足切りする。draft には適用しない（draftは
# レビューを待っているのではなく、まだ出していない状態で、しきい値の意味が違う）
REVIEW_WAITING_HOURS = 24

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


def _latest_decisive_review(
    reviews: list[GitHubReview],
) -> dict[int, GitHubReview]:
    """PR番号 → 最後に承認状態を動かしたレビュー（APPROVED / CHANGES_REQUESTED）。

    COMMENTED を数に入れないのが要点。インラインコメントは GitHub 上 COMMENTED の
    レビューになるが、これは「見た」以上のことを表明していない。実際のチームでは
    レビューの過半がこれになるため、「レビューが1件でも付いたか」で判定すると、

    - 修正を求められたまま止まっているPR（最後が CHANGES_REQUESTED）
    - コメントだけ付いて承認されていないPR

    の両方が attention から落ちる。前者は有志チームで最も多い停滞で、後者は
    「見られてはいるが終わっていない」状態のまま誰の目にも入らなくなる。

    キャッシュにpushの時刻が無いため「作者が直したがまだ再レビューされていない」区別は
    付かない。ここで判定できるのは承認状態だけで、誰の番かは判定していない。
    """
    latest: dict[int, GitHubReview] = {}
    for review in reviews:
        if review.submitted_at is None or is_excluded_login(review.reviewer_login):
            continue
        if review.state.upper() not in _DECISIVE_REVIEW_STATES:
            continue
        current = latest.get(review.pr_number)
        if current is None or review.submitted_at > current.submitted_at:
            latest[review.pr_number] = review
    return latest


def _attention(
    entries: list[ChangeLogEntry],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    now: datetime,
) -> Attention:
    """止まっているものを集める。

    PR側を変化ログのエントリから作るのは、行と注記の食い違いを避けるため。除外規則
    （bot・unknown）や時刻の採用がそちらと自動的に揃う。

    OPEN なPRの振り分けは、最後に承認状態を動かしたレビューだけで決める。

    - CHANGES_REQUESTED → 修正待ち
    - APPROVED          → 出さない（終わっている）
    - どちらも無い      → レビュー待ち（無レビューでも、コメントだけでも）

    「レビューが1件でもあるか」では判定しない。インラインコメントは COMMENTED の
    レビューになり、実際のチームではレビューの過半を占める。それを「レビュー済み」と
    数えると、コメントが付いただけのPRがどの群にも入らず画面から消える。

    ここで判定しているのは承認状態であって「誰の番か」ではない。コメントが質問なら
    待っているのは作者だが、pushの時刻を持たないため区別できない。だから作者側の
    見出しは「あなたのPRが止まっています」という事実の言い方にしてある。
    """
    review_wanted: list[AttentionPullRequest] = []
    drafts: list[AttentionPullRequest] = []
    changes_requested: list[ChangesRequestedPullRequest] = []
    latest_review = _latest_decisive_review(reviews)

    for entry in entries:
        if entry.kind != "pull_request" or entry.state != "open":
            continue
        if entry.notes.draft:
            drafts.append(_attention_pr(entry, now))
            continue
        decisive = latest_review.get(entry.number)
        if decisive is not None and decisive.state.upper() == "CHANGES_REQUESTED":
            changes_requested.append(
                ChangesRequestedPullRequest(
                    number=entry.number,
                    title=entry.title,
                    author_login=entry.actor_login,
                    html_url=entry.html_url,
                    reviewer_login=decisive.reviewer_login,
                    requested_at=decisive.submitted_at,
                    waiting_hours=_hours_since(decisive.submitted_at, now),
                )
            )
        elif decisive is None:
            pr = _attention_pr(entry, now)
            if pr.waiting_hours >= REVIEW_WAITING_HOURS:
                review_wanted.append(pr)

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
    changes_requested.sort(key=lambda p: p.waiting_hours, reverse=True)
    drafts.sort(key=lambda p: p.waiting_hours, reverse=True)
    stalled.sort(key=lambda i: i.stalled_hours, reverse=True)
    return Attention(
        review_wanted=review_wanted,
        changes_requested=changes_requested,
        drafts=drafts,
        stalled_issues=stalled,
    )


def _recently_done(entries: list[ChangeLogEntry], limit: int) -> list[DoneItem]:
    """片づいたものを新しい順に。

    attention が「止まっているもの」しか出さないため、この画面は放っておくと負の情報
    だけを毎日見せる面になる。無給の有志チームでは進んだ実感が継続の燃料なので、
    同じデータの裏返しを並べて釣り合いを取る。

    人ごとの件数には畳まない。畳んだ瞬間に「誰が多いか」の序列になり、この画面が
    出さないと決めた集約に戻る（docs/scoring_design.md「数字の降格」）。

    closed のPR（マージされずに閉じたもの）は成果ではないので採らない。Issueの
    not_planned は changelog が別状態として持つのでここには入ってこない。
    """
    done = [
        entry
        for entry in entries
        if (entry.kind == "pull_request" and entry.state == "merged")
        or (entry.kind == "issue" and entry.state == "closed")
    ]
    done.sort(key=lambda e: e.occurred_at, reverse=True)
    return [
        DoneItem(
            kind=entry.kind,
            number=entry.number,
            title=entry.title,
            actor_login=entry.actor_login,
            html_url=entry.html_url,
            occurred_at=entry.occurred_at,
        )
        for entry in done[:limit]
    ]


def _previous_total(
    entries: list[ChangeLogEntry], now: datetime, days: int, tz_offset_minutes: int
) -> int:
    """直前の同じ長さの期間の件数。

    「直近14日で23件」だけでは、それが多いのか少ないのかを読み手が判断できない。
    比べる相手を1つ添えるだけで、同じ数字が増減の情報になる。
    """
    today = _local_date(now, tz_offset_minutes)
    start = today - timedelta(days=days * 2 - 1)
    end = today - timedelta(days=days)
    return sum(
        1
        for entry in entries
        if start <= _local_date(entry.occurred_at, tz_offset_minutes) <= end
    )


def _namespace_of(label: str) -> str | None:
    """ラベルの名前空間（"epic:core1" → "epic"）。

    「動いている領域」に task / priority:low / triage が混ざると、上位を占めるのは
    ワークフロー用のラベルばかりになり、領域が読めない。名前空間で分けておけば、
    フロントが領域らしい群を独立して並べられる。除外リストを持たないのは、
    どの接頭辞が領域かはチームのラベル運用ごとに違うため。
    """
    head, sep, rest = label.partition(":")
    if not sep or not head.strip() or not rest.strip():
        return None
    # strip した値は返さない。フロントは namespace の長さでラベルを切って残りを
    # 表示するので、ここで長さが変わると（"epic :core1" のような空白入りラベルで）
    # 切り出し位置がずれる。namespace は「":" より前の生の文字列」で通す
    return head


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
            namespace=_namespace_of(label),
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
        pulse_previous_total=_previous_total(
            changelog.entries, now, days, tz_offset_minutes
        ),
        attention=_attention(changelog.entries, issues, reviews, now),
        recently_done=_recently_done(changelog.entries, RECENTLY_DONE_LIMIT),
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
