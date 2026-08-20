"""3カテゴリのスコアを計算する。

スコアはDBに保存せず、キャッシュ済みGitHubデータ（PR・Issue・Review）から都度計算する。
計算ロジックが変わっても再計算コストが発生しないのが設計意図（docs/data_model.md）。

正規化方針（docs/scoring_design.md）:
- 相対スコア = 個人の値 ÷ チーム合計値。各カテゴリはメンバー間で合計1.0になる
- 総合スコア = Σ(カテゴリ重み × カテゴリ相対スコア)。重みは値を持つカテゴリだけで合計1.0に
  正規化するため、総合スコアもメンバー間で合計1.0（＝分配比率）になる

レスポンスの weights はプロジェクトの設定値をそのまま返す。データが無いカテゴリがあると
実際に効く重みはその分だけ再配分されるが、これは分配比率の式に織り込み済みの挙動であり、
設定値そのものは画面3の重み編集が参照するため書き換えない。
"""

from collections.abc import Iterable
from statistics import median_low

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_cache import GitHubIssue, GitHubPullRequest, GitHubReview
from app.models.project import Project
from app.repositories.github_cache import GitHubCacheRepository
from app.repositories.project import ProjectRepository
from app.schemas.project import CategoryWeights
from app.schemas.score import CategoryScores, MemberScore, ScoreResponse
from app.services.github import ensure_synced, fetch_and_store

_APPROVE_OR_CHANGES = {"APPROVED", "CHANGES_REQUESTED"}


def _is_excluded(login: str) -> bool:
    """スコア対象外のログイン。

    "unknown" は services/github.py の _actor_login が、GitHubアカウント削除等で login を
    取得できなかったときに入れるフォールバック値。実在の貢献者ではないため、複数の削除済み
    アカウントの活動が1人分に合算された幽霊メンバーになるのを防ぐ。
    """
    return login.endswith("[bot]") or login == "unknown"


def _collect_logins(
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    registered_logins: Iterable[str] = (),
) -> set[str]:
    """スコア対象となる貢献者のGitHubログイン集合（bot・unknown除く）。

    キャッシュに現れる全人物に加え、まだ活動のないVallog登録メンバーも含める。
    活動がなければ全カテゴリ0のままだが、ダッシュボードから存在ごと消えないようにする。
    """
    logins: set[str] = set(registered_logins)
    for pr in prs:
        logins.add(pr.author_login)
    for issue in issues:
        logins.add(issue.author_login)
        for a in issue.assignees:
            logins.add(a.login)
    for r in reviews:
        logins.add(r.reviewer_login)
    return {login for login in logins if not _is_excluded(login)}


def _shares(values: dict[str, float]) -> dict[str, float] | None:
    """各メンバーの値をチーム合計で割った相対スコア。合計が0（データなし）ならNone。"""
    total = sum(values.values())
    if total <= 0:
        return None
    return {login: value / total for login, value in values.items()}


def _combine_equal(
    sub_metrics: Iterable[dict[str, float]], logins: set[str]
) -> dict[str, float]:
    """複数のサブ指標を均等割りで合成する（docs/scoring_design.md「カテゴリ内の合成: 均等割り」）。

    各サブ指標を相対スコア（合計1.0）に正規化してから平均する。値を持つサブ指標のみを分母に
    数えるため、合成結果もメンバー間で合計1.0になる（全サブ指標が0なら全員0.0）。
    """
    share_dicts = [s for s in (_shares(m) for m in sub_metrics) if s is not None]
    if not share_dicts:
        return {login: 0.0 for login in logins}
    return {
        login: sum(s.get(login, 0.0) for s in share_dicts) / len(share_dicts)
        for login in logins
    }


def _activity_relative(
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    logins: set[str],
) -> dict[str, float]:
    """GitHub活動量（40%）。4サブ指標を均等割りで合成した相対スコア。"""
    pr_author = {pr.number: pr.author_login for pr in prs}
    authored = {login: 0.0 for login in logins}
    for pr in prs:
        if pr.author_login in authored:
            authored[pr.author_login] += 1
    for issue in issues:
        if issue.author_login in authored:
            authored[issue.author_login] += 1

    review_comments = {login: 0.0 for login in logins}
    approve_changes = {login: 0.0 for login in logins}
    for r in reviews:
        if r.reviewer_login not in review_comments:
            continue
        if _is_self_review(r, pr_author):
            continue
        if r.comment_count > 0 or r.body.strip():
            review_comments[r.reviewer_login] += 1
        if r.state in _APPROVE_OR_CHANGES:
            approve_changes[r.reviewer_login] += 1

    turnaround = _turnaround_values(prs, reviews, logins)

    return _combine_equal([authored, review_comments, approve_changes, turnaround], logins)


def _is_self_review(review: GitHubReview, pr_author: dict[int, str]) -> bool:
    """PR作者自身によるレビューか。GitHubはPR作者が自分のPRにインラインコメントを付けると
    作者名義のCOMMENTEDレビューを作る。これをレビュー貢献・TATに数えると、セルフコメントで
    レビュー数が水増しされ、PR作成直後（経過時間ほぼ0）のTATが応答性を不当に押し上げるため除外する。
    """
    return review.reviewer_login == pr_author.get(review.pr_number)


def _turnaround_values(
    prs: list[GitHubPullRequest], reviews: list[GitHubReview], logins: set[str]
) -> dict[str, float]:
    """レビューのターンアラウンドタイムを「速いほど高い」応答性の値に変換する。

    PR到着→レビュー提出までの時間を時間単位で平均し、1/(1+平均時間)で0〜1に写像する。
    正規化（個人÷チーム合計）に載せられるよう「多い/速いほど高い」向きに揃える。
    """
    pr_created = {pr.number: pr.gh_created_at for pr in prs}
    pr_author = {pr.number: pr.author_login for pr in prs}
    total_hours: dict[str, float] = {login: 0.0 for login in logins}
    counts: dict[str, int] = {login: 0 for login in logins}
    for r in reviews:
        if r.reviewer_login not in total_hours or r.submitted_at is None:
            continue
        if _is_self_review(r, pr_author):
            continue
        created = pr_created.get(r.pr_number)
        if created is None:
            continue
        hours = (r.submitted_at - created).total_seconds() / 3600
        if hours < 0:
            continue
        total_hours[r.reviewer_login] += hours
        counts[r.reviewer_login] += 1

    responsiveness: dict[str, float] = {}
    for login in logins:
        if counts[login] == 0:
            responsiveness[login] = 0.0
        else:
            avg_hours = total_hours[login] / counts[login]
            responsiveness[login] = 1 / (1 + avg_hours)
    return responsiveness


# 経過時間の下限（時間）。アサイン直後にクローズされたIssueで SP÷ごく短時間 の
# 巨大値が出るのを抑える。プロトタイプ準拠（max(hours, 0.1)）
_MIN_ELAPSED_HOURS = 0.1


def _speed_values(issues: list[GitHubIssue], logins: set[str]) -> dict[str, float]:
    """タスク完了スピード（35%）の生値。獲得SP ÷ クランプ後の経過時間。

    タスク分割に中立にするため、メンバー単位で「総獲得SP ÷ 総経過時間」を取る。
    Issueごとに SP/時間 を出して足し上げると、同じ仕事を細かく分割するほどスコアが
    膨らむ（SP5×1件=0.1 に対し SP1×5件=0.5）ため、分割数に依存しない総量比にする。
    物量は活動量（起票数）と品質（マージPR数）で既に報われている。

    経過時間は、SP付きクローズIssueの担当者単位のチーム中央値を上限にする。偶数件では
    2つの中央候補のうち小さい値を採り、少数データで長期Issueが上限を急増させるのを防ぐ。
    not_planned は成果ではないためSPを加えず、同じ中央値だけ分母に加える。中央値の母集団は
    state_reason に依存しないため、同じIssueを完了へ変えても上限は変わらず、完了が必ず有利になる。
    state_reason 未取得（NULL、次回同期前の既存キャッシュ）は completed 相当として扱う。
    複数アサインの場合は各担当者を満額で評価する。

    assigned_at は /issues/events から集計するが、取得件数に上限（MAX_EVENT_PAGES）があるため、
    アサイン済みでもイベントが窓から溢れて None になりうる。その場合は起点をIssue作成時刻に
    代替する。資料の計測区間「アサインから」からは外れ、アサイン待ち時間の分だけ経過時間が
    長く出るが、完了した獲得SPが丸ごとスコアから消えるより実態に近い。
    """
    samples: list[tuple[str, int, float, bool]] = []
    for issue in issues:
        if issue.story_points is None or issue.closed_at is None:
            continue
        for a in issue.assignees:
            if a.login not in logins:
                continue
            start = a.assigned_at or issue.gh_created_at
            elapsed_hours = (issue.closed_at - start).total_seconds() / 3600
            samples.append(
                (
                    a.login,
                    issue.story_points,
                    max(elapsed_hours, _MIN_ELAPSED_HOURS),
                    issue.state_reason == "not_planned",
                )
            )

    if not samples:
        return {login: 0.0 for login in logins}
    elapsed_cap = median_low(hours for _, _, hours, _ in samples)

    sp_sum = {login: 0 for login in logins}
    hours_sum = {login: 0.0 for login in logins}
    for login, story_points, elapsed_hours, stopped in samples:
        hours_sum[login] += elapsed_cap if stopped else min(elapsed_hours, elapsed_cap)
        if not stopped:
            sp_sum[login] += story_points

    return {
        login: sp_sum[login] / hours_sum[login] if hours_sum[login] > 0 else 0.0
        for login in logins
    }


def _quality_values(
    prs: list[GitHubPullRequest],
    reviews: list[GitHubReview],
    logins: set[str],
) -> dict[str, float]:
    """品質・可用性（25%）の生値。可用性から手戻りを差し引く。

    可用性は「他者にApproveされた自分のマージ済みPR数」を代理指標とする
    （docs/scoring_design.md「実装者以外のメンバーがレビュー・検証」）。
    手戻りはPR再オープン回数のみで数え、PR作者に帰属させる。scoring_design.md は
    「バグ報告数 + PR再オープン回数」と定義するが、バグ報告を正しい原因者に帰属させる
    手段がキャッシュに無いため、MVPでは再オープンのみとする（バグ報告の帰属は #75 で設計）。
    """
    approvers_by_pr: dict[int, set[str]] = {}
    for r in reviews:
        if r.state == "APPROVED":
            approvers_by_pr.setdefault(r.pr_number, set()).add(r.reviewer_login)

    values = {login: 0.0 for login in logins}
    for pr in prs:
        if pr.author_login not in values:
            continue
        external_approvers = approvers_by_pr.get(pr.number, set()) - {pr.author_login}
        if pr.merged_at is not None and external_approvers:
            values[pr.author_login] += 1
        values[pr.author_login] -= pr.reopened_count

    return {login: max(0.0, v) for login, v in values.items()}


def compute_scores(
    project: Project,
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    registered_logins: Iterable[str] = (),
    weights: CategoryWeights | None = None,
) -> ScoreResponse:
    """キャッシュ済みGitHubデータからプロジェクトのスコアを計算する（純粋関数・DBアクセスなし）。

    weights はプロジェクトのデフォルト重みの上書き。分配案ごとに別の重みで比較する
    ユースケース（画面7）のために受け取る。
    """
    weights = weights or CategoryWeights(
        activity=project.weight_activity,
        speed=project.weight_speed,
        quality=project.weight_quality,
    )
    logins = _collect_logins(prs, issues, reviews, registered_logins)
    zeros = {login: 0.0 for login in logins}

    activity = _activity_relative(prs, issues, reviews, logins)
    speed = _shares(_speed_values(issues, logins)) or zeros
    quality = _shares(_quality_values(prs, reviews, logins)) or zeros

    # データが無いカテゴリ（例: SPラベル未運用でスピードが全員0）はその重みを配分せず、
    # 値を持つカテゴリだけで重みを正規化する。全員のスコアを同じ定数で割ることと等価なので
    # 順位も分配比率も変わらず、docs/scoring_design.md の
    # 「分配比率 = 総合スコア ÷ チーム全体の総合スコア合計」と一致した上で合計1.0を保てる。
    active = [
        (values, weight)
        for values, weight in (
            (activity, weights.activity),
            (speed, weights.speed),
            (quality, weights.quality),
        )
        if sum(values.values()) > 0
    ]
    active_weight_total = sum(weight for _, weight in active)

    def _total_for(login: str) -> float:
        if active_weight_total <= 0:
            return 0.0
        return sum(
            weight / active_weight_total * values[login] for values, weight in active
        )

    members = [
        MemberScore(
            github_login=login,
            categories=CategoryScores(
                activity=activity[login],
                speed=speed[login],
                quality=quality[login],
            ),
            total=_total_for(login),
        )
        for login in sorted(logins)
    ]
    members.sort(key=lambda m: m.total, reverse=True)
    return ScoreResponse(weights=weights, members=members)


async def get_project_scores(
    db: AsyncSession,
    project: Project,
    access_token: str,
    force: bool = False,
    weights: CategoryWeights | None = None,
) -> ScoreResponse:
    """TTLに従いGitHubキャッシュを最新化してからスコアを計算する。

    force はダッシュボードの手動リフレッシュ（TTLを無視した強制再同期）の布石。
    現状ルーターからは常に False だが、公開時にクエリパラメータで渡せるよう残す。
    """
    await ensure_synced(db, project, access_token, fetch_and_store, force=force)

    cache = GitHubCacheRepository(db)
    prs = await cache.list_pull_requests(project.id)
    issues = await cache.list_issues(project.id)
    reviews = await cache.list_reviews(project.id)
    members = await ProjectRepository(db).list_member_users(project.id)
    return compute_scores(
        project,
        prs,
        issues,
        reviews,
        registered_logins=[u.github_login for u in members],
        weights=weights,
    )
