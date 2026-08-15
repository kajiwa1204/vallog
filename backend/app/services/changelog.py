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
    """PR作者以外の人間による最初のレビュー。

    PR作者が自分のPRにインラインコメントを付けるとGitHubは作者名義のCOMMENTEDレビューを
    作る。これを「レビューされた」と数えるとセルフコメントだけでレビュー済みに見えてしまう
    ため除外する（services/scoring.py の _is_self_review と同じ理由）。

    bot（coderabbit等）のレビューも除外する。botのレビュー行は一覧に出さない方針なので、
    ここで数えると「他者レビュー済み・待ち時間3.2h」と注記されているのに、その根拠となる
    行がログのどこにも無い状態になる。注記は必ず一覧上で辿れる、が変化ログの前提であり、
    検証できない注記を出すのはその前提を壊す。services/scoring.py も bot を除いた
    ログイン集合でループするため数えておらず、揃えないと同じデータから画面ごとに違う
    事実が出る。
    """
    external = [
        r
        for r in reviews
        if r.reviewer_login != pr.author_login
        and not is_excluded_login(r.reviewer_login)
        and r.submitted_at is not None
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
        id=f"pull_request:{pr.number}",
        kind="pull_request",
        number=pr.number,
        title=pr.title,
        actor_login=pr.author_login,
        state="merged" if pr.merged_at is not None else pr.state,
        occurred_at=pr.merged_at or pr.closed_at or pr.gh_created_at,
        html_url=pr.html_url,
        notes=ChangeLogNotes(
            first_review_hours=(
                _elapsed_hours(pr.gh_created_at, first_review.submitted_at)
                if first_review is not None
                else None
            ),
            reviewed_by_others=first_review is not None,
            reopened_count=pr.reopened_count,
            draft=pr.draft,
        ),
    )


def _issue_state(issue: GitHubIssue) -> str:
    """却下・重複でのクローズを完了と区別する。

    GitHubはどちらも state="closed" にするため、state_reason を見ないと
    「片付けた仕事」と「着手せず閉じた起票」が同じ見た目で並ぶ。変化ログは #18 で
    分配の根拠（レシート）として読まれるので、この2つは分けて出す必要がある。
    services/scoring.py も同じ理由で not_planned をスピード集計から除外している。

    state_reason 未取得（NULL、次回同期前の既存キャッシュ）は completed 相当として扱う。
    """
    if issue.state == "closed" and issue.state_reason == "not_planned":
        return "not_planned"
    return issue.state


def _issue_entry(issue: GitHubIssue) -> ChangeLogEntry:
    return ChangeLogEntry(
        id=f"issue:{issue.number}",
        kind="issue",
        number=issue.number,
        title=issue.title,
        actor_login=issue.author_login,
        state=_issue_state(issue),
        occurred_at=issue.closed_at or issue.gh_created_at,
        html_url=issue.html_url,
        notes=ChangeLogNotes(story_points=issue.story_points),
    )


def _review_entry(review: GitHubReview, pr: GitHubPullRequest) -> ChangeLogEntry:
    return ChangeLogEntry(
        id=f"review:{review.github_id}",
        kind="review",
        number=review.pr_number,
        title=pr.title,
        actor_login=review.reviewer_login,
        state=review.state.lower(),
        occurred_at=review.submitted_at,
        html_url=review.html_url,
        notes=ChangeLogNotes(
            response_hours=_elapsed_hours(pr.gh_created_at, review.submitted_at)
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

    同じPRへの複数レビューは畳まず、レビュー1件を1行として出す。GitHubはインラインコメントの
    バッチごとに別レビューを作るため1つのPRで数行を占めうるが、会話が往復した事実そのもの
    なので潰さない。limit を食う問題は has_more で「続きがある」と伝える方向で解く。
    実画面（#13）で読みづらければ (pr_number, reviewer_login) 単位の畳み込みを再検討する。
    """
    # `?member=` のように値なしで渡ると FastAPI は "" を入れる。そのまま絞り込むと誰にも
    # 一致せず0件になり、フロントには「データが無い」と区別が付かないため未指定に倒す
    member = member or None

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
        # 対象PRの作者がbotでも、人間が出したレビューは残す（除外はレビュアー本人にだけ
        # かける）。レビューは責任を伴う実労働で、依存更新PRのレビューも例外ではない。
        # ここを落とすと、セキュリティ更新を丁寧に見ている人の仕事が #18 の分配根拠から
        # まるごと消える。bot作者のPR行自体は上のループで除いているので、そのレビュー行は
        # 対応するPR行を持たないまま並ぶが、一覧はフラットな時系列でタイトルと一次リンクを
        # 各行が持つため読みに支障はない。
        # bot のPRが常態化（dependabot導入等）してノイズが問題になったら、落とすのではなく
        # 「対象がbot」の注記を足してフロント側で畳む方向に倒す。
        if review.reviewer_login == pr.author_login:
            continue
        entries.append(_review_entry(review, pr))

    entries.sort(key=lambda e: e.occurred_at, reverse=True)
    # 全件読んでから切れるのは、キャッシュ自体が同期側で頭打ちになっているため
    # （services/github.py の MAX_LIST_PAGES 参照）
    return ChangeLogResponse(entries=entries[:limit], has_more=len(entries) > limit)


def roster_logins(
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
) -> list[str]:
    """変化ログを絞り込める顔ぶれ（純粋関数・DBアクセスなし）。

    **`build_changelog(member=X)` が1件以上返す X だけを載せる**、が満たすべき性質。
    絞ったのに0件になるチップは、押した人に「自分の記録が消えた」と読ませる。
    だから上の build_changelog と同じ判定を使い、同じファイルに隣接して置く
    （離すと片方だけ直されて静かにずれる）。

    Issueの担当者を含めるのが要点。エントリの actor_login は常に起票者なので、
    担当しかしていない人はログの行のどこにも名前が出ないが、その人で絞れば行は返る。
    エントリから顔ぶれを作ると、この人たちが丸ごと落ちる。

    並びは大文字小文字を無視した辞書順。活動量順にしないのは、ダッシュボードが
    出さないと決めた序列がチップに現れるため（docs/screen_design.md 画面4）。
    """
    pr_by_number = {pr.number: pr for pr in prs}
    logins: set[str] = set()

    for pr in prs:
        if is_excluded_login(pr.author_login):
            continue
        logins.add(pr.author_login)

    for issue in issues:
        if is_excluded_login(issue.author_login):
            continue
        logins.update(
            login for login in _issue_logins(issue) if not is_excluded_login(login)
        )

    for review in reviews:
        if review.submitted_at is None:
            continue
        if is_excluded_login(review.reviewer_login):
            continue
        pr = pr_by_number.get(review.pr_number)
        if pr is None:
            continue
        if review.reviewer_login == pr.author_login:
            continue
        logins.add(review.reviewer_login)

    return sorted(logins, key=str.lower)


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
