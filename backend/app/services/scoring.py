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

import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.models.github_cache import GitHubIssue, GitHubPullRequest, GitHubReview
from app.models.project import Project
from app.repositories.distribution import DistributionRepository
from app.repositories.github_cache import GitHubCacheRepository
from app.repositories.project import ProjectRepository
from app.schemas.project import CategoryWeights
from app.schemas.score import (
    CategoryScores,
    MemberFacts,
    MemberScore,
    ScoreResponse,
)
from app.services.changelog import NOT_DONE_STATE_REASONS
from app.services.github import ensure_synced, fetch_and_store, is_excluded_github_actor

_APPROVE_OR_CHANGES = {"APPROVED", "CHANGES_REQUESTED"}


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
    return {login for login in logins if not is_excluded_github_actor(login)}


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


def _turnaround_totals(
    prs: list[GitHubPullRequest], reviews: list[GitHubReview], logins: set[str]
) -> tuple[dict[str, float], dict[str, int]]:
    """レビュアーごとの (レビュー応答時間の合計, 対象レビュー件数)。

    スコア（_turnaround_values）と生事実の平均TAT（_member_facts）が**同じ集計から**
    値を取るために切り出してある。数え直すと、除外条件（セルフレビュー・submitted_at
    欠落・負の経過時間）が片方だけ直された日に、同じ画面でスコアの根拠と表示中の事実が
    食い違う。
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
    return total_hours, counts


def _turnaround_values(
    prs: list[GitHubPullRequest], reviews: list[GitHubReview], logins: set[str]
) -> dict[str, float]:
    """レビューのターンアラウンドタイムを「速いほど高い」応答性の値に変換する。

    PR到着→レビュー提出までの時間を時間単位で平均し、1/(1+平均時間)で0〜1に写像する。
    正規化（個人÷チーム合計）に載せられるよう「多い/速いほど高い」向きに揃える。
    """
    total_hours, counts = _turnaround_totals(prs, reviews, logins)

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


def _sp_totals(
    issues: list[GitHubIssue], logins: set[str]
) -> tuple[dict[str, int], dict[str, float]]:
    """担当者ごとの (完了Issueで獲得したSPの合計, 経過時間の合計)。

    Issueのclosed_atを完了時刻の代理とする（GitHubはPRマージ時に紐づくIssueを自動クローズするため）。
    却下・重複でクローズされたIssue（NOT_DONE_STATE_REASONS）は成果ではないため除外する。
    判定は services/changelog.py と同じ定数を引く（片方だけ直されると、同じデータから
    画面とスコアで違う事実が出る）。
    state_reason 未取得（NULL、次回同期前の既存キャッシュ）は completed 相当として計上する。
    複数アサインの場合は各担当者を満額で評価する。

    assigned_at は /issues/events から集計するが、取得件数に上限（MAX_EVENT_PAGES）があるため、
    アサイン済みでもイベントが窓から溢れて None になりうる。その場合は起点をIssue作成時刻に
    代替する。資料の計測区間「アサインから」からは外れ、アサイン待ち時間の分だけ経過時間が
    長く出るが、完了した獲得SPが丸ごとスコアから消えるより実態に近い。

    スコア（_speed_values）と生事実の獲得SP（_member_facts）が**同じ集計から**値を取る
    ために切り出してある。SPが「担当者にのみ配られる」ことは両者で必ず一致していなければ
    ならず、数え直すとその一致が偶然に頼ることになる。
    """
    sp_sum = {login: 0 for login in logins}
    hours_sum = {login: 0.0 for login in logins}
    for issue in issues:
        if issue.story_points is None or issue.closed_at is None:
            continue
        if issue.state_reason in NOT_DONE_STATE_REASONS:
            continue
        for a in issue.assignees:
            if a.login not in sp_sum:
                continue
            start = a.assigned_at or issue.gh_created_at
            elapsed_hours = (issue.closed_at - start).total_seconds() / 3600
            sp_sum[a.login] += issue.story_points
            hours_sum[a.login] += max(elapsed_hours, _MIN_ELAPSED_HOURS)
    return sp_sum, hours_sum


def _speed_values(issues: list[GitHubIssue], logins: set[str]) -> dict[str, float]:
    """タスク完了スピード（35%）の生値。獲得SP ÷ 経過時間（アサイン〜完了）。

    タスク分割に中立にするため、メンバー単位で「総獲得SP ÷ 総経過時間」を取る。
    Issueごとに SP/時間 を出して足し上げると、同じ仕事を細かく分割するほどスコアが
    膨らむ（SP5×1件=0.1 に対し SP1×5件=0.5）ため、分割数に依存しない総量比にする。
    物量は活動量（起票数）と品質（マージPR数）で既に報われている。
    """
    sp_sum, hours_sum = _sp_totals(issues, logins)
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


def _member_facts(
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    logins: set[str],
) -> dict[str, MemberFacts]:
    """スコアに潰す前の生事実（画面7の「レシート」）。

    振り返りの根拠を点数分解（+0.06 等）ではなく事実の積み上げで示すために公開する。
    ここに並ぶのは相対化も重み付けもしない実数なので、他のカテゴリの値に引きずられない。

    各値は上のスコア計算が使うのと同じ関数・同じ除外条件から取る（_sp_totals /
    _turnaround_totals / _is_self_review）。ここで数え直さないのは、除外条件が
    片方だけ更新された日に、同じ画面で「スコアの根拠」と「並んでいる事実」が
    静かに食い違うため。

    ただし件数の内訳ではないので「和＝合計」の関係は無い。**この関数が答えるのは
    「誰の何を数えたか」だけ**で、それは MemberFacts のフィールド名に書いてある。
    """
    pr_author = {pr.number: pr.author_login for pr in prs}
    sp_sum, _ = _sp_totals(issues, logins)
    total_hours, review_counts = _turnaround_totals(prs, reviews, logins)

    authored = {login: 0 for login in logins}
    reopened = {login: 0 for login in logins}
    for pr in prs:
        if pr.author_login not in authored:
            continue
        authored[pr.author_login] += 1
        reopened[pr.author_login] += pr.reopened_count

    # 出したレビューの件数。活動量スコアはこれを「コメント付き」と「Approve/変更要求」の
    # 2つのサブ指標に分けて使っているため、総数そのものはスコアに現れない。事実としては
    # 「何本レビューしたか」のほうが読めるので、除外条件だけスコアと揃えて総数を出す
    submitted = {login: 0 for login in logins}
    for r in reviews:
        if r.reviewer_login not in submitted:
            continue
        if _is_self_review(r, pr_author):
            continue
        submitted[r.reviewer_login] += 1

    return {
        login: MemberFacts(
            story_points_earned=sp_sum[login],
            pull_requests_authored=authored[login],
            reviews_submitted=submitted[login],
            pull_requests_reopened=reopened[login],
            # 対象レビューが0件のときに0.0を返すと「即座に返した」と読めてしまう。
            # 平均が定義できないことは NULL で言う
            avg_review_turnaround_hours=(
                total_hours[login] / review_counts[login]
                if review_counts[login] > 0
                else None
            ),
        )
        for login in logins
    }


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
    facts = _member_facts(prs, issues, reviews, logins)

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
            facts=facts[login],
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


# 未確定の案が「分配を議論している最中」と見なされる期間。最終更新からこの日数を
# 過ぎるとスコアは非開示に戻る。
#
# 期限を設けないと、誰かが案を作って放置しただけでスコアが**永久に開いたまま**になる。
# #100 は「1回目の分配以降ずっと見えたまま」を避けるために finalized を条件に入れたが、
# 確定されない案はその条件をすり抜けるため、次の作業期間がまるごと汚染される。
#
# 30日にしたのは、分配の議論が数週間に及ぶことはあっても月をまたいで続くことは想定
# しないため。長い議論の途中で落ちないだけの余裕を持たせつつ、放置された案が次の
# 作業期間まで開示を引きずらない長さにしている。
SCORE_DISCLOSURE_WINDOW_DAYS = 30


async def can_disclose_scores(db: AsyncSession, project_id: uuid.UUID) -> bool:
    """スコアをクライアントに開示してよい状態か（#100）。

    「振り返りのとき」を、**最近動いた未確定の分配案**が存在することで判定する。

        案が0件                    → 非開示（作業期間中）
        未確定で最近動いた案がある → 開示（分配を議論している最中）
        全部確定済み               → 非開示（議論が終わった）
        未確定だが30日動いていない → 非開示（議論が立ち消えた）

    新しいテーブルもフェーズ状態も持たないのは、分配案の作成をトリガーにすると
    「変化ログを読む → 議論する → 案を作る → 初めてスコアが見える」という順序まで
    構造で強制できるため（docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
    フェーズ状態は単なるスイッチで、この順序までは担保しない。

    確定済みに戻して非開示にしても情報は失われない。確定した案は DistributionItem に
    当時の数値を保持しており、隠れるのはライブのスコアだけ。放置で閉じた場合も、案を
    編集すればまた開く（最終更新が動くため）。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=SCORE_DISCLOSURE_WINDOW_DAYS)
    return await DistributionRepository(db).exists_unfinalized(project_id, cutoff)


def resolve_weights(
    activity: int | None, speed: int | None, quality: int | None
) -> CategoryWeights | None:
    """クエリで渡された重みを CategoryWeights にする。3つ揃っていなければ拒否する。

    **足りない分を既定値で埋めない。** 埋めると、利用者が指定していない重みが黙って
    混ざったスコアが 200 で返る。画面7は「配分」と「その根拠」が同じ重みの産物である
    ことに依存しているので、片方だけ別の重みで計算された値が正しい根拠として並び、
    誰も気づけない。3つ揃わないなら答えを返さないほうが安全。

    1つも指定が無いのは「プロジェクト既定で計算せよ」という正当な指定なので None を返す。
    """
    given = (activity, speed, quality)
    if all(w is None for w in given):
        return None
    if any(w is None for w in given):
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorCode.SCORES_WEIGHTS_INCOMPLETE,
            "weight_activity, weight_speed and weight_quality must be given together",
        )
    return CategoryWeights(activity=activity, speed=speed, quality=quality)


async def get_scores_for_disclosure(
    db: AsyncSession,
    project: Project,
    access_token: str,
    weights: CategoryWeights | None = None,
) -> ScoreResponse:
    """クライアントへ返すスコア。開示条件を満たさなければ 403 で拒否する。

    ゲートを get_project_scores() の中ではなくこの関数に置くのが要点。
    services/distribution.py が案の作成・重み変更時に get_project_scores() を呼んで
    初期比率を作っているため、そこまで塞ぐと鶏卵問題になる（案を作れないので
    スコアが見えず、スコアが見えないので案が作れない）。制限するのは**クライアントへの
    開示**であって、サーバ内部の計算ではない。

    誰でも分配案を作れるので、ダミーの案を作ればスコアは見られる。これは技術的な壁では
    なく、受け入れた制約（#100）。created_by が記録され編集履歴は全員に公開されるため、
    見えるかたちで意図的な行為をする必要がある、という社会的抑止で担保する。

    weights は分配案ごとの重みの上書き。**指定を受け取れるようにしてあるのが重要**で、
    案の配分比率は案の重みで計算されるのに、スコアだけプロジェクト既定の重みで返すと、
    同じ画面に並ぶ「配分」と「その根拠」が別々の重みの産物になる。重みを動かして複数案を
    比較すること自体が②固定を折る施策なので、そこで根拠が食い違うと施策ごと壊れる。
    """
    if not await can_disclose_scores(db, project.id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            ErrorCode.SCORES_NOT_DISCLOSED,
            "Scores are disclosed only while an unfinalized distribution proposal exists",
        )
    return await get_project_scores(db, project, access_token, weights=weights)
