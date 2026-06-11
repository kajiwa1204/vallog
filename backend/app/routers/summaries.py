from fastapi import APIRouter

from app.repositories.github_cache import GitHubCacheRepository
from app.repositories.summary import SummaryRepository
from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.summary import SummaryResponse
from app.services import claude as claude_service
from app.services.github import ensure_cache

router = APIRouter(tags=["summaries"])


@router.get(
    "/projects/{project_id}/summaries", response_model=list[SummaryResponse]
)
async def list_summaries(project: MemberProject, db: DB):
    summaries = await SummaryRepository(db).list_for_project(project.id)
    return [SummaryResponse.model_validate(s) for s in summaries]


@router.post(
    "/projects/{project_id}/summaries/{login}", response_model=SummaryResponse
)
async def generate_summary(
    login: str, project: MemberProject, user: CurrentUser, db: DB
):
    project = await ensure_cache(db, project, user)
    cache = GitHubCacheRepository(db)
    summary = await claude_service.generate_summary(
        SummaryRepository(db),
        project.id,
        login,
        await cache.list_pull_requests(project.id),
        await cache.list_issues(project.id),
        await cache.list_reviews(project.id),
    )
    await db.commit()
    return SummaryResponse.model_validate(summary)
