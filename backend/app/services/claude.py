import hashlib
import uuid

import anthropic
from fastapi import HTTPException, status

from app.core.config import settings
from app.models import (
    ContributionSummary,
    GitHubIssue,
    GitHubPullRequest,
    GitHubReview,
)
from app.repositories.summary import SummaryRepository

SYSTEM_PROMPT = """あなたは開発チームの貢献を記録するテクニカルライターです。
GitHubの活動データをもとに、指定されたメンバーの貢献サマリーを日本語で書いてください。

ルール:
- 事実ベースで書く。データにない働きを推測・誇張しない
- 担当した領域・特徴的な貢献・チームへの影響を3〜5段落で構成する
- 根拠としてPR番号・Issue番号（例: #12）を本文中に引用する
- 就活や実績証明にそのまま使える、簡潔で具体的な文体にする
- 見出しや箇条書きは使わず、文章として書く"""


def build_member_context(
    login: str,
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
) -> str:
    lines = [f"対象メンバー: {login}", "", "## 作成したPull Request"]
    for p in prs:
        if p.author_login != login:
            continue
        state = "merged" if p.merged_at else p.state
        lines.append(f"- #{p.number} {p.title} ({state})")
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


def context_hash(context: str) -> str:
    return hashlib.sha256(context.encode()).hexdigest()


async def generate_summary(
    summary_repo: SummaryRepository,
    project_id: uuid.UUID,
    login: str,
    prs: list[GitHubPullRequest],
    issues: list[GitHubIssue],
    reviews: list[GitHubReview],
) -> ContributionSummary:
    context = build_member_context(login, prs, issues, reviews)
    digest = context_hash(context)

    # 生成コストがかかるため、元データが変わっていなければキャッシュを返す
    cached = await summary_repo.get(project_id, login)
    if cached is not None and cached.context_hash == digest:
        return cached

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claude APIキーが未設定のため、貢献サマリーを生成できません。",
        )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )
    content = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="貢献サマリーの生成に失敗しました。",
        )

    return await summary_repo.upsert(project_id, login, content, digest)
