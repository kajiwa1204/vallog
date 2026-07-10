from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.repositories.github_cache import GitHubCacheRepository
from app.repositories.summary import PRSummaryRepository, SummaryRepository
from app.repositories.summary_job import SummaryJobRepository
from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.summary import PRSummaryItem, SummaryJobResponse, SummaryResponse
from app.services import summary as summary_service

router = APIRouter(tags=["summaries"])


@router.get(
    "/projects/{project_id}/summaries", response_model=list[SummaryResponse]
)
async def list_summaries(project: MemberProject, db: DB):
    summaries = await SummaryRepository(db).list_for_project(project.id)
    return [SummaryResponse.model_validate(s) for s in summaries]


@router.post("/projects/{project_id}/summaries/{login}")
async def generate_summary(
    login: str, project: MemberProject, user: CurrentUser, db: DB
):
    """メンバー一括サマリー生成ジョブをキューに積む。

    アクティブなジョブが既にあれば 200 でそれを返す（重複起動防止）。
    新規作成時は 202 Accepted でジョブ情報を返す。
    """
    job, created = await summary_service.enqueue_summary_job(db, project.id, login)
    if created:
        summary_service.launch_summary_job(job.id, project.id, user.id, login)

    return JSONResponse(
        status_code=202 if created else 200,
        content=SummaryJobResponse.model_validate(job).model_dump(mode="json"),
    )


@router.post("/projects/{project_id}/summaries/{login}/prs/{pr_number}")
async def generate_pr_summary(
    login: str, pr_number: int, project: MemberProject, user: CurrentUser, db: DB
):
    """PR単独サマリー生成ジョブをキューに積む。

    同一PRのアクティブジョブがあれば 200 でそれを返す（重複起動防止）。
    新規作成時は 202 Accepted でジョブ情報を返す。
    """
    job, created = await summary_service.enqueue_summary_job(
        db, project.id, login, pr_number
    )
    if created:
        summary_service.launch_summary_job(
            job.id, project.id, user.id, login, pr_number
        )

    return JSONResponse(
        status_code=202 if created else 200,
        content=SummaryJobResponse.model_validate(job).model_dump(mode="json"),
    )


@router.get(
    "/projects/{project_id}/summary-jobs",
    response_model=list[SummaryJobResponse],
)
async def list_summary_jobs(project: MemberProject, db: DB):
    """メンバーごとの最新ジョブ一覧を返す(メンバー一括ジョブのみ)。"""
    jobs = await SummaryJobRepository(db).list_latest_per_member(project.id)
    return [SummaryJobResponse.model_validate(j) for j in jobs]


@router.get(
    "/projects/{project_id}/summaries/{login}/prs",
    response_model=list[PRSummaryItem],
)
async def list_pr_summaries(login: str, project: MemberProject, db: DB):
    """loginが author のPR一覧を、PRサマリーとPR単独ジョブをマージして返す。"""
    cache_repo = GitHubCacheRepository(db)
    prs = await cache_repo.list_pull_requests(project.id)
    author_prs = [p for p in prs if p.author_login == login]

    pr_summary_repo = PRSummaryRepository(db)
    summaries_by_number = {
        ps.pr_number: ps
        for ps in await pr_summary_repo.list_for_author(project.id, login)
    }

    job_repo = SummaryJobRepository(db)
    jobs_by_pr = await job_repo.list_latest_per_pr(project.id, login)

    items = [
        PRSummaryItem(
            pr_number=pr.number,
            title=pr.title,
            html_url=pr.html_url,
            state=summary_service.derive_pr_state(pr),
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
