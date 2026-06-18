import asyncio
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import (
    GitHubIssue,
    GitHubPullRequest,
    GitHubReview,
    PRSummary,
    User,
)
from app.models.summary import SummaryJob
from app.repositories.github_cache import GitHubCacheRepository
from app.repositories.project import ProjectRepository
from app.repositories.summary import PRSummaryRepository, SummaryRepository
from app.repositories.summary_job import SummaryJobRepository
from app.services import llm as llm_service
from app.services.github import GitHubClient, ensure_cache

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
        result += f"\n(以降 {skipped} ファイルの差分は省略)"
    return result


def _pr_context_hash(
    pr: GitHubPullRequest,
    reviews: list[GitHubReview],
) -> str:
    """PRサマリーのキャッシュキー。head_shaが変わればdiffも変わったとみなす。

    diff本体はハッシュに含めない。head_shaの変化で再生成を判定することで、
    キャッシュ確認時にGitHub APIを呼ばずに済む。
    プロバイダとモデル名を含めることで、切替時に混在品質が生じるのを防ぐ。
    """
    if settings.summary_provider == "openai":
        model = settings.openai_pr_summary_model
    else:
        model = settings.claude_pr_summary_model

    pr_reviews = [rv for rv in reviews if rv.pr_number == pr.number]
    review_part = "|".join(
        f"{rv.reviewer_login}:{rv.state}:{rv.body[:200]}" for rv in pr_reviews[:10]
    )
    raw = (
        f"{pr.title}\n{pr.body or ''}\n{pr.head_sha or ''}"
        f"\n{review_part}\n{settings.summary_provider}\n{model}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _member_context_hash(login: str, pr_summaries: list[PRSummary]) -> str:
    """メンバーサマリーのキャッシュキー。PR要約の内容が変わったら再生成する。"""
    if settings.summary_provider == "openai":
        model = settings.openai_member_summary_model
    else:
        model = settings.claude_member_summary_model

    pr_part = "|".join(f"{ps.pr_number}:{ps.content[:100]}" for ps in pr_summaries)
    raw = f"{login}\n{pr_part}\n{settings.summary_provider}\n{model}"
    return hashlib.sha256(raw.encode()).hexdigest()


def build_pr_context(
    pr: GitHubPullRequest, reviews: list[GitHubReview], diff: str
) -> str:
    state = "merged" if pr.merged_at else ("draft" if pr.draft else pr.state)
    body_text = pr.body[:2000] if pr.body else "(本文なし)"
    lines = [
        f"PR #{pr.number}: {pr.title}",
        f"状態: {state}",
        "",
        "## 本文(補助情報)",
        body_text,
        "",
        "## コード差分(diff)",
        diff or "(差分なし)",
        "",
        "## レビューコメント",
    ]
    pr_reviews = [rv for rv in reviews if rv.pr_number == pr.number]
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
    """PRの表示用state文字列を導出する。build_pr_contextと同じロジックをサービス層に切り出す。"""
    if pr.merged_at:
        return "merged"
    if pr.draft:
        return "draft"
    return pr.state


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

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise RuntimeError(f"User {user_id} not found")

    project_repo = ProjectRepository(db)
    project = await project_repo.get(project_id)
    if project is None:
        raise RuntimeError(f"Project {project_id} not found")

    project = await ensure_cache(db, project, user)

    cache_repo = GitHubCacheRepository(db)
    prs = await cache_repo.list_pull_requests(project_id)
    issues = await cache_repo.list_issues(project_id)
    reviews = await cache_repo.list_reviews(project_id)

    pr_summary_repo = PRSummaryRepository(db)

    if pr_number is not None:
        await _run_single_pr_job(
            db, job, project, project_id, login, pr_number,
            prs, reviews, pr_summary_repo,
            GitHubClient(user.github_access_token),
        )
        return

    await _run_member_batch_job(
        db, job, project, project_id, login,
        prs, issues, reviews, pr_summary_repo,
        GitHubClient(user.github_access_token),
    )


async def _run_single_pr_job(
    db: AsyncSession,
    job: SummaryJob,
    project,
    project_id: uuid.UUID,
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

    if settings.summary_provider == "claude" and not settings.anthropic_api_key:
        raise RuntimeError(
            "Claude APIキーが未設定のため、貢献サマリーを生成できません。"
            "SUMMARY_PROVIDER=openai でローカルLLM等に切り替えることもできます。"
        )

    try:
        raw_diff = await gh_client.fetch_pr_diff(
            project.repo_owner, project.repo_name, pr_number
        )
        diff = _trim_diff(raw_diff)
        context = build_pr_context(target, reviews, diff)
        content = await llm_service.chat(PR_SYSTEM_PROMPT, context, "pr", 1024)
    except Exception as e:
        detail = e.detail if isinstance(e, HTTPException) else str(e)
        raise RuntimeError(f"PR #{pr_number} のサマリー生成に失敗しました: {detail}") from e

    if not content:
        raise RuntimeError(f"PR #{pr_number} のサマリー生成結果が空でした。再実行してください。")

    digest = _pr_context_hash(target, reviews)
    await pr_summary_repo.upsert(project_id, pr_number, login, content, digest)
    job.done_prs = 1
    await db.commit()

    job.status = "succeeded"
    job.finished_at = datetime.now(timezone.utc)
    await db.commit()


async def _run_member_batch_job(
    db: AsyncSession,
    job: SummaryJob,
    project,
    project_id: uuid.UUID,
    login: str,
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
    pr_summary_repo: PRSummaryRepository,
    gh_client: GitHubClient,
) -> None:
    """メンバー一括ジョブ: ハッシュ変化分のPR要約 + メンバーサマリーを生成する。"""
    existing = {
        ps.pr_number: ps
        for ps in await pr_summary_repo.list_for_author(project_id, login)
    }

    author_prs = [p for p in prs if p.author_login == login]
    to_generate = [
        pr for pr in author_prs
        if pr.number not in existing
        or existing[pr.number].context_hash != _pr_context_hash(pr, reviews)
    ]

    job.total_prs = len(to_generate)
    await db.commit()

    if to_generate and settings.summary_provider == "claude" and not settings.anthropic_api_key:
        raise RuntimeError(
            "Claude APIキーが未設定のため、貢献サマリーを生成できません。"
            "SUMMARY_PROVIDER=openai でローカルLLM等に切り替えることもできます。"
        )

    concurrency = llm_service._resolve_concurrency("pr")
    failed_prs: list[int] = []

    for i in range(0, len(to_generate), concurrency):
        batch = to_generate[i: i + concurrency]

        async def _generate_one(pr: GitHubPullRequest) -> tuple[GitHubPullRequest, str | None]:
            # diff取得もLLM呼び出しも個別に捕捉し、1件の失敗でバッチ内の成功分(課金済み)を失わない
            try:
                raw_diff = await gh_client.fetch_pr_diff(
                    project.repo_owner, project.repo_name, pr.number
                )
                diff = _trim_diff(raw_diff)
                context = build_pr_context(pr, reviews, diff)
                content = await llm_service.chat(PR_SYSTEM_PROMPT, context, "pr", 1024)
                return pr, content or None
            except Exception as e:
                detail = e.detail if isinstance(e, HTTPException) else str(e)
                logger.warning("PR #%d summary failed: %s", pr.number, detail)
                return pr, None

        results = await asyncio.gather(*(_generate_one(pr) for pr in batch))

        for pr, content in results:
            if content:
                digest = _pr_context_hash(pr, reviews)
                await pr_summary_repo.upsert(
                    project_id, pr.number, pr.author_login, content, digest
                )
                job.done_prs += 1
            else:
                failed_prs.append(pr.number)
        await db.commit()

    if failed_prs:
        # 不完全なPR要約集合からメンバーサマリーを作ると誤った内容になるため生成しない。
        # 成功分はコミット済みなので、再実行すると失敗分のみが再試行される
        numbers = ", ".join(f"#{n}" for n in failed_prs)
        raise RuntimeError(
            f"一部のPRサマリー生成に失敗しました（{numbers}）。再実行すると失敗分のみ再試行されます。"
        )

    pr_summaries = await pr_summary_repo.list_for_author(project_id, login)
    member_context = build_member_context(login, pr_summaries, issues, reviews)
    member_digest = _member_context_hash(login, pr_summaries)

    summary_repo = SummaryRepository(db)
    cached = await summary_repo.get(project_id, login)
    if cached is None or cached.context_hash != member_digest:
        member_content = await llm_service.chat(
            MEMBER_SYSTEM_PROMPT, member_context, "member", 4096
        )
        if not member_content:
            raise RuntimeError("メンバーサマリーの生成結果が空でした。再実行してください。")
        await summary_repo.upsert(project_id, login, member_content, member_digest)
        await db.commit()

    job.status = "succeeded"
    job.finished_at = datetime.now(timezone.utc)
    await db.commit()


def _launch_summary_job(
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
