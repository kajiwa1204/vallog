import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import InvitationLink, Project, User
from app.repositories.github_cache import GitHubCacheRepository
from app.repositories.project import ProjectRepository
from app.repositories.summary import SummaryRepository
from app.schemas.project import (
    CategoryWeights,
    InvitationCreateResponse,
    MemberResponse,
    ProjectCreate,
)
from app.schemas.score import (
    MemberDetailResponse,
    MemberScore,
    ScoreResponse,
)
from app.schemas.summary import SummaryResponse
from app.services import scoring
from app.services.github import GitHubClient, ensure_cache

INVITATION_TTL = timedelta(days=7)


def _weights_of(project: Project) -> CategoryWeights:
    return CategoryWeights(
        activity=project.weight_activity,
        speed=project.weight_speed,
        quality=project.weight_quality,
    )


async def create_project(
    db: AsyncSession, user: User, payload: ProjectCreate
) -> Project:
    repo = ProjectRepository(db)
    if await repo.get_by_repo(payload.repo_owner, payload.repo_name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="このリポジトリはすでにVallogに登録されています",
        )
    gh_repo = await GitHubClient(user.github_access_token).get_repo(
        payload.repo_owner, payload.repo_name
    )
    if gh_repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="リポジトリが見つからないか、アクセス権がありません",
        )
    project = Project(
        name=payload.name or payload.repo_name,
        repo_owner=payload.repo_owner,
        repo_name=payload.repo_name,
    )
    await repo.create(project)
    await repo.add_member(project.id, user.id)
    await db.commit()
    return project


async def registered_member_map(
    db: AsyncSession, project_id: uuid.UUID
) -> dict[str, str | None]:
    users = await ProjectRepository(db).list_member_users(project_id)
    return {u.github_login: u.avatar_url for u in users}


async def list_members(
    db: AsyncSession, project: Project, user: User
) -> list[MemberResponse]:
    """GitHubのコントリビューター（キャッシュ由来）とVallog登録メンバーを統合する。"""
    project = await ensure_cache(db, project, user)
    cache = GitHubCacheRepository(db)
    prs = await cache.list_pull_requests(project.id)
    issues = await cache.list_issues(project.id)
    reviews = await cache.list_reviews(project.id)
    registered = await registered_member_map(db, project.id)

    logins: set[str] = set(registered)
    logins.update(p.author_login for p in prs)
    logins.update(i.author_login for i in issues)
    logins.update(a.login for i in issues for a in i.assignees)
    logins.update(r.reviewer_login for r in reviews)

    return [
        MemberResponse(
            github_login=login,
            avatar_url=registered.get(login) or f"https://github.com/{login}.png",
            is_registered=login in registered,
        )
        for login in sorted(logins)
        if not login.endswith("[bot]") and login != "unknown"
    ]


async def compute_project_scores(
    db: AsyncSession, project: Project, user: User, force: bool = False
) -> ScoreResponse:
    project = await ensure_cache(db, project, user, force=force)
    cache = GitHubCacheRepository(db)
    prs = await cache.list_pull_requests(project.id)
    issues = await cache.list_issues(project.id)
    reviews = await cache.list_reviews(project.id)
    registered = await registered_member_map(db, project.id)
    members = scoring.compute_scores(
        prs, issues, reviews, _weights_of(project), registered
    )
    return ScoreResponse(
        synced_at=project.github_synced_at,
        weights=_weights_of(project),
        members=members,
    )


async def get_member_detail(
    db: AsyncSession, project: Project, user: User, login: str
) -> MemberDetailResponse:
    project = await ensure_cache(db, project, user)
    cache = GitHubCacheRepository(db)
    prs = await cache.list_pull_requests(project.id)
    issues = await cache.list_issues(project.id)
    reviews = await cache.list_reviews(project.id)
    registered = await registered_member_map(db, project.id)
    members = scoring.compute_scores(
        prs, issues, reviews, _weights_of(project), registered
    )
    score = next((m for m in members if m.github_login == login), None)
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )
    timeline = scoring.build_timeline(login, prs, issues, reviews)
    recent_prs, recent_issues, recent_reviews = scoring.recent_items_for_member(
        login, prs, issues, reviews
    )
    cached_summary = await SummaryRepository(db).get(project.id, login)
    return MemberDetailResponse(
        score=score,
        weights=_weights_of(project),
        synced_at=project.github_synced_at,
        timeline=timeline,
        recent_prs=recent_prs,
        recent_issues=recent_issues,
        recent_reviews=recent_reviews,
        summary=(
            SummaryResponse.model_validate(cached_summary)
            if cached_summary
            else None
        ),
    )


async def create_invitation(
    db: AsyncSession, project: Project, user: User
) -> InvitationCreateResponse:
    invitation = InvitationLink(
        token=secrets.token_urlsafe(32),
        project_id=project.id,
        created_by=user.id,
        expires_at=datetime.now(timezone.utc) + INVITATION_TTL,
    )
    await ProjectRepository(db).create_invitation(invitation)
    await db.commit()
    return InvitationCreateResponse(
        token=invitation.token,
        url=f"{settings.frontend_url}/invite/{invitation.token}",
        expires_at=invitation.expires_at,
    )


async def get_valid_invitation(db: AsyncSession, token: str) -> InvitationLink:
    invitation = await ProjectRepository(db).get_invitation(token)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="招待リンクが見つかりません"
        )
    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="招待リンクの有効期限が切れています"
        )
    return invitation


async def join_via_invitation(
    db: AsyncSession, token: str, user: User
) -> Project:
    invitation = await get_valid_invitation(db, token)
    project = invitation.project
    # privateリポジトリの場合、アクセス権のないGitHubアカウントの参加を拒否する
    gh_repo = await GitHubClient(user.github_access_token).get_repo(
        project.repo_owner, project.repo_name
    )
    if gh_repo is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このリポジトリへのアクセス権がないため参加できません",
        )
    await ProjectRepository(db).add_member(project.id, user.id)
    await db.commit()
    return project
