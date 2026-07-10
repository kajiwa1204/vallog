"""貢献サマリーの2層キャッシュ生成サービス。

Tier 1 = pr_summaries: PRごとに生成。head_sha が変わった場合のみ再生成する
（マージ済みPRは不変なので一度生成したら再課金されない）。
Tier 2 = contribution_summaries: Tier 1集合 + Issue/Review実績から生成。
Tier 1の内容が変わった場合のみ再生成する。
"""

import asyncio
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import GitHubIssue, GitHubPullRequest, GitHubReview, PRSummary
from app.models.summary import SummaryJob
from app.repositories.github_cache import GitHubCacheRepository
from app.repositories.project import ProjectRepository
from app.repositories.summary import PRSummaryRepository, SummaryRepository
from app.repositories.summary_job import SummaryJobRepository
from app.repositories.user import UserRepository
from app.schemas.summary import PRSummaryItem, SummaryJobResponse
from app.services.github import GitHubClient, ensure_synced, fetch_and_store
from app.services.llm import SummaryUseCase, get_llm_client

logger = logging.getLogger(__name__)

PR_SYSTEM_PROMPT = """あなたは開発チームの貢献を記録するテクニカルライターです。
コード差分(diff)からこのPRが何を実装・修正・改善したかを技術的に読み解いて2〜4文の日本語で要約してください。

ルール:
- 2〜4文の文章で書く。見出しや箇条書きは使わない
- 事実ベースで書く。データにない働きを推測・誇張しない
- PR本文は補助情報として参照してよいが、変更されたファイル・実装内容などdiffから読み取れる事実を優先する
- レビューでの指摘対応など、PRの質に関わる情報があれば含める"""

MEMBER_SYSTEM_PROMPT = """あなたは開発チームの貢献を記録するテクニカルライターです。
GitHubの活動データをもとに、指定されたメンバーの貢献サマリーを日本語で書いてください。

ルール:
- 事実ベースで書く。データにない働きを推測・誇張しない
- 担当した領域・特徴的な貢献・チームへの影響を3〜5段落で構成する
- 根拠としてPR番号・Issue番号（例: #12）を本文中に引用する
- 就活や実績証明にそのまま使える、簡潔で具体的な文体にする
- 見出しや箇条書きは使わず、文章として書く"""

# 1バッチあたりのPRサマリー同時生成数。GitHubのdiff取得を束ねる単位で、
# LLM呼び出し自体の同時実行数は llm 側のセマフォが別途制御する
_PR_BATCH_SIZE = 5

# バックグラウンドタスクへの参照を保持し、GCで消されないようにする
_background_tasks: set[asyncio.Task] = set()

_LOCKFILE_PATTERNS = re.compile(
    r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|uv\.lock|poetry\.lock"
    r"|.*\.min\.js|.*\.min\.css|.*\.svg|.*\.map|.*\.snap)$"
)


def _trim_diff(raw_diff: str) -> str:
    """lockファイル等を除外し、文字数上限に収めたdiffを返す。"""
    files = re.split(r"(?=^diff --git )", raw_diff, flags=re.MULTILINE)
    selected: list[str] = []
    total = 0
    skipped = 0
    for chunk in files:
        if not chunk.strip():
            continue
        header_match = re.match(r"diff --git a/(.*?) b/", chunk)
        if header_match:
            path = header_match.group(1)
            if _LOCKFILE_PATTERNS.search(path):
                continue
        truncated = chunk[:8000]
        if total + len(truncated) > settings.pr_diff_char_limit:
            skipped += 1
            continue
        selected.append(truncated)
        total += len(truncated)

    result = "".join(selected)
    if skipped:
        # 上限超過分は並び順の途中でも飛ばすため「以降」とは限らない。位置に依らず正確な表現にする
        result += f"\n(他 {skipped} ファイルの差分は文字数上限により省略)"
    return result


def reviews_for_pr(reviews: list[GitHubReview], pr_number: int) -> list[GitHubReview]:
    """指定PRのレビューを決定的な順序で返す。

    submitted_at は NULL 可（PENDING等）で、DBの返却順に依存すると同一データでも
    context_hash が揺れて無駄にTier1を再生成してしまう。github_id（GitHub採番で
    単調増加）の降順で安定ソートし、並び順と [:10] の選択を決定的にする。
    ハッシュ計算(pr_context_hash)と生成入力(build_pr_context)の両方で使う。
    """
    return sorted(
        (rv for rv in reviews if rv.pr_number == pr_number),
        key=lambda rv: rv.github_id,
        reverse=True,
    )


def _digest(payload: object) -> str:
    """入力構造をJSONで正規化して指紋化する。

    区切り文字（':' '|'）でフィールドを連結すると、タイトルや本文に区切り文字が
    含まれたときに別入力が同一文字列になり、ハッシュ衝突で再生成が漏れる（stale）。
    JSONは各フィールドを構造的に分離しエスケープするため、この混入を防ぐ。
    """
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def pr_context_hash(
    pr: GitHubPullRequest, reviews: list[GitHubReview], cache_prefix: str
) -> str:
    """Tier 1（PRサマリー）のキャッシュキー。

    diff本体はハッシュに含めず、head_shaの変化でdiffの変化を検知する。
    これによりキャッシュ判定時にGitHub APIを呼ばずに済む。
    cache_prefix（プロバイダ:モデル名）を含めることで、切替時に旧モデルの
    サマリーが混在するのを防ぐ。
    """
    pr_reviews = reviews_for_pr(reviews, pr.number)
    payload = {
        "title": pr.title,
        "body": pr.body or "",
        "head_sha": pr.head_sha or "",
        "reviews": [
            [rv.reviewer_login, rv.state, rv.body[:200]] for rv in pr_reviews[:10]
        ],
        "prefix": cache_prefix,
    }
    return _digest(payload)


def member_context_hash(
    login: str,
    pr_summaries: list[PRSummary],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    cache_prefix: str,
) -> str:
    """Tier 2（メンバーサマリー）のキャッシュキー。

    build_member_context と同じ入力（Tier 1要約 + 当人が作成/担当したIssue +
    当人が実施したReview）を、同じ絞り込み・決定的な並びで指紋化する。
    Tier 1だけでなくIssue/Reviewの変化でも再生成されるよう、生成入力と
    ハッシュ入力を一致させる。
    """
    member_issues = sorted(
        (
            i
            for i in issues
            if i.author_login == login or any(a.login == login for a in i.assignees)
        ),
        key=lambda i: i.number,
    )
    member_reviews = sorted(
        (rv for rv in reviews if rv.reviewer_login == login),
        key=lambda rv: rv.github_id,
    )
    payload = {
        "login": login,
        "prs": [[ps.pr_number, ps.content] for ps in pr_summaries],
        "issues": [
            [
                i.number,
                i.title,
                i.state,
                "author" if i.author_login == login else "assignee",
                list(i.labels or []),
            ]
            for i in member_issues
        ],
        "reviews": [[rv.pr_number, rv.state, rv.body[:200]] for rv in member_reviews],
        "prefix": cache_prefix,
    }
    return _digest(payload)


def select_prs_to_generate(
    author_prs: list[GitHubPullRequest],
    existing: dict[int, PRSummary],
    reviews: list[GitHubReview],
    cache_prefix: str,
) -> list[GitHubPullRequest]:
    """Tier 1の再生成対象を選ぶ。未生成 or context_hash 不一致のPRのみ返す。"""
    return [
        pr
        for pr in author_prs
        if pr.number not in existing
        or existing[pr.number].context_hash != pr_context_hash(pr, reviews, cache_prefix)
    ]


def build_pr_context(
    pr: GitHubPullRequest, reviews: list[GitHubReview], diff: str
) -> str:
    body_text = pr.body[:2000] if pr.body else "(本文なし)"
    lines = [
        f"PR #{pr.number}: {pr.title}",
        f"状態: {derive_pr_state(pr)}",
        "",
        "## 本文(補助情報)",
        body_text,
        "",
        "## コード差分(diff)",
        diff or "(差分なし)",
        "",
        "## レビューコメント",
    ]
    pr_reviews = reviews_for_pr(reviews, pr.number)
    for rv in pr_reviews[:10]:
        comment = rv.body.strip().replace("\n", " ")[:200]
        suffix = f": {comment}" if comment else ""
        lines.append(f"- {rv.reviewer_login} ({rv.state}){suffix}")
    return "\n".join(lines)


def build_member_context(
    login: str,
    pr_summaries: list[PRSummary],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
) -> str:
    lines = [f"対象メンバー: {login}", "", "## 作成したPull Requestの貢献内容"]
    for ps in pr_summaries:
        lines.append(f"- #{ps.pr_number} {ps.content}")
    lines.append("")
    lines.append("## 作成・担当したIssue")
    for i in issues:
        if i.author_login == login or any(a.login == login for a in i.assignees):
            role = "作成" if i.author_login == login else "担当"
            labels = f" [{', '.join(i.labels)}]" if i.labels else ""
            lines.append(f"- #{i.number} {i.title} ({role}/{i.state}){labels}")
    lines.append("")
    lines.append("## 実施したコードレビュー")
    for rv in reviews:
        if rv.reviewer_login != login:
            continue
        comment = rv.body.strip().replace("\n", " ")[:200]
        suffix = f": {comment}" if comment else ""
        lines.append(f"- PR #{rv.pr_number} ({rv.state}){suffix}")
    return "\n".join(lines)


def derive_pr_state(pr: GitHubPullRequest) -> str:
    """PRの表示用state文字列を導出する。"""
    if pr.merged_at:
        return "merged"
    if pr.draft:
        return "draft"
    return pr.state


async def list_member_pr_summaries(
    db: AsyncSession, project_id: uuid.UUID, login: str
) -> list[PRSummaryItem]:
    """loginが author のPR一覧を、生成済みPRサマリーと最新のPR単独ジョブをマージして返す。

    複数リポジトリの取得結果を突き合わせて集約するため、routerではなくservicesに置く。
    """
    prs = await GitHubCacheRepository(db).list_pull_requests(project_id)
    author_prs = [p for p in prs if p.author_login == login]

    summaries_by_number = {
        ps.pr_number: ps
        for ps in await PRSummaryRepository(db).list_for_author(project_id, login)
    }
    jobs_by_pr = await SummaryJobRepository(db).list_latest_per_pr(project_id, login)

    items = [
        PRSummaryItem(
            pr_number=pr.number,
            title=pr.title,
            html_url=pr.html_url,
            state=derive_pr_state(pr),
            content=(
                summaries_by_number[pr.number].content
                if pr.number in summaries_by_number
                else None
            ),
            generated_at=(
                summaries_by_number[pr.number].generated_at
                if pr.number in summaries_by_number
                else None
            ),
            job=(
                SummaryJobResponse.model_validate(jobs_by_pr[pr.number])
                if pr.number in jobs_by_pr
                else None
            ),
        )
        for pr in author_prs
    ]
    # 新しいPRが先頭に来るよう降順ソート
    items.sort(key=lambda x: x.pr_number, reverse=True)
    return items


async def enqueue_summary_job(
    db: AsyncSession,
    project_id: uuid.UUID,
    login: str,
    pr_number: int | None = None,
) -> tuple[SummaryJob, bool]:
    """アクティブ（pending/running）ジョブがあれば返し、なければ作成する。

    get_active→create の間に別リクエストが割り込む TOCTOU があるため、DBの部分ユニーク
    制約（uq_summary_jobs_active_member / _active_pr）で二重作成を弾く。競合で作成に
    失敗したら既存のアクティブジョブを返す。戻り値は (job, created) で、created=True の
    ときだけ呼び出し側がバックグラウンド生成を起動する。
    """
    job_repo = SummaryJobRepository(db)

    active = await job_repo.get_active(project_id, login, pr_number)
    if active is not None:
        return active, False

    try:
        job = await job_repo.create(project_id, login, pr_number)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await job_repo.get_active(project_id, login, pr_number)
        if existing is None:
            raise
        return existing, False

    return job, True


async def run_summary_job(
    job_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    login: str,
    pr_number: int | None = None,
) -> None:
    """バックグラウンドでサマリーを生成するジョブ。

    リクエストのセッションは使えないため、新しいDBセッションを自前で開く。
    """
    async with AsyncSessionLocal() as db:
        job_repo = SummaryJobRepository(db)
        job = await job_repo.get(job_id)
        if job is None:
            logger.error("SummaryJob %s not found", job_id)
            return

        try:
            await _run_job_inner(db, job, project_id, user_id, login, pr_number)
        except Exception as e:
            logger.exception("SummaryJob %s failed: %s", job_id, e)
            await db.rollback()
            async with AsyncSessionLocal() as err_db:
                err_job = await SummaryJobRepository(err_db).get(job_id)
                if err_job is not None:
                    err_job.status = "failed"
                    err_job.error = str(e)
                    err_job.finished_at = datetime.now(timezone.utc)
                    await err_db.commit()


async def _run_job_inner(
    db: AsyncSession,
    job: SummaryJob,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    login: str,
    pr_number: int | None = None,
) -> None:
    job.status = "running"
    await db.commit()

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise RuntimeError(f"User {user_id} not found")

    project = await ProjectRepository(db).get(project_id)
    if project is None:
        raise RuntimeError(f"Project {project_id} not found")

    project = await ensure_synced(db, project, user.github_access_token, fetch_and_store)

    cache_repo = GitHubCacheRepository(db)
    prs = await cache_repo.list_pull_requests(project_id)
    issues = await cache_repo.list_issues(project_id)
    reviews = await cache_repo.list_reviews(project_id)

    pr_summary_repo = PRSummaryRepository(db)

    async with GitHubClient(user.github_access_token) as gh_client:
        if pr_number is not None:
            await _run_single_pr_job(
                db, job, project, login, pr_number, prs, reviews,
                pr_summary_repo, gh_client,
            )
        else:
            await _run_member_batch_job(
                db, job, project, login, prs, issues, reviews,
                pr_summary_repo, gh_client,
            )


async def _generate_pr_summary(
    project,
    pr: GitHubPullRequest,
    reviews: list[GitHubReview],
    gh_client: GitHubClient,
) -> str:
    raw_diff = await gh_client.fetch_pr_diff(
        project.repo_owner, project.repo_name, pr.number
    )
    diff = _trim_diff(raw_diff)
    context = build_pr_context(pr, reviews, diff)
    result = await get_llm_client().complete(PR_SYSTEM_PROMPT, context, SummaryUseCase.PR)
    return result.content


async def _run_single_pr_job(
    db: AsyncSession,
    job: SummaryJob,
    project,
    login: str,
    pr_number: int,
    prs: list[GitHubPullRequest],
    reviews: list[GitHubReview],
    pr_summary_repo: PRSummaryRepository,
    gh_client: GitHubClient,
) -> None:
    """PR単独ジョブ: 指定PR1件を強制再生成する。ハッシュ一致でもスキップしない。"""
    target = next(
        (p for p in prs if p.author_login == login and p.number == pr_number),
        None,
    )
    if target is None:
        raise RuntimeError(
            f"PR #{pr_number} が見つかりません。このメンバーが author のPRではないか、"
            "GitHubキャッシュを更新する必要があります。"
        )

    job.total_prs = 1
    await db.commit()

    try:
        content = await _generate_pr_summary(project, target, reviews, gh_client)
    except Exception as e:
        detail = e.detail if isinstance(e, HTTPException) else str(e)
        raise RuntimeError(f"PR #{pr_number} のサマリー生成に失敗しました: {detail}") from e

    cache_prefix = get_llm_client().cache_key_prefix(SummaryUseCase.PR)
    digest = pr_context_hash(target, reviews, cache_prefix)
    await pr_summary_repo.upsert(project.id, pr_number, login, content, digest)
    job.done_prs = 1
    job.status = "succeeded"
    job.finished_at = datetime.now(timezone.utc)
    await db.commit()


async def _run_member_batch_job(
    db: AsyncSession,
    job: SummaryJob,
    project,
    login: str,
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    pr_summary_repo: PRSummaryRepository,
    gh_client: GitHubClient,
) -> None:
    """メンバー一括ジョブ: ハッシュ変化分のPR要約(Tier1) + メンバーサマリー(Tier2)を生成する。"""
    llm = get_llm_client()
    pr_prefix = llm.cache_key_prefix(SummaryUseCase.PR)

    existing = {
        ps.pr_number: ps
        for ps in await pr_summary_repo.list_for_author(project.id, login)
    }
    author_prs = [p for p in prs if p.author_login == login]
    to_generate = select_prs_to_generate(author_prs, existing, reviews, pr_prefix)

    job.total_prs = len(to_generate)
    await db.commit()

    failed_prs: list[int] = []

    # バッチごとにcommitし、途中で落ちても生成済み(課金済み)の分を失わない
    for i in range(0, len(to_generate), _PR_BATCH_SIZE):
        batch = to_generate[i : i + _PR_BATCH_SIZE]

        async def _generate_one(pr: GitHubPullRequest) -> tuple[GitHubPullRequest, str | None]:
            # 1件の失敗でバッチ内の成功分を失わないよう、個別に捕捉する
            try:
                return pr, await _generate_pr_summary(project, pr, reviews, gh_client)
            except Exception as e:
                detail = e.detail if isinstance(e, HTTPException) else str(e)
                logger.warning("PR #%d summary failed: %s", pr.number, detail)
                return pr, None

        results = await asyncio.gather(*(_generate_one(pr) for pr in batch))

        for pr, content in results:
            if content:
                digest = pr_context_hash(pr, reviews, pr_prefix)
                await pr_summary_repo.upsert(
                    project.id, pr.number, pr.author_login, content, digest
                )
                job.done_prs += 1
            else:
                failed_prs.append(pr.number)
        await db.commit()

    pr_summaries = await pr_summary_repo.list_for_author(project.id, login)

    if failed_prs:
        numbers = ", ".join(f"#{n}" for n in failed_prs)
        if not pr_summaries:
            # 生成できたTier1が1件もない（トークン失効・全面障害等）ならTier2は作らない。
            # 成功分はコミット済みなので、再実行すると失敗分のみが再試行される
            raise RuntimeError(
                f"全てのPRサマリー生成に失敗しました（{numbers}）。再実行すると失敗分のみ再試行されます。"
            )
        # 巨大diff等で恒久的に取得できないPRが混じっても、取得できたTier1だけで
        # メンバーサマリーを生成する。1件の失敗でメンバー全体が永久にブロックされるのを防ぐ。
        # 失敗分は次回実行で再試行され、成功すれば pr_summaries が変わって自動で作り直される
        logger.warning(
            "Member %s: %d PR summary(ies) failed (%s); building Tier2 from %d available",
            login, len(failed_prs), numbers, len(pr_summaries),
        )

    member_prefix = llm.cache_key_prefix(SummaryUseCase.MEMBER)
    member_digest = member_context_hash(
        login, pr_summaries, issues, reviews, member_prefix
    )

    summary_repo = SummaryRepository(db)
    cached = await summary_repo.get(project.id, login)
    if cached is None or cached.context_hash != member_digest:
        member_context = build_member_context(login, pr_summaries, issues, reviews)
        result = await llm.complete(MEMBER_SYSTEM_PROMPT, member_context, SummaryUseCase.MEMBER)
        await summary_repo.upsert(project.id, login, result.content, member_digest)
        await db.commit()

    job.status = "succeeded"
    job.finished_at = datetime.now(timezone.utc)
    await db.commit()


def launch_summary_job(
    job_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    login: str,
    pr_number: int | None = None,
) -> None:
    """asyncio.create_task でジョブを起動し、参照を保持してGCを防ぐ。"""
    task = asyncio.create_task(
        run_summary_job(job_id, project_id, user_id, login, pr_number)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
