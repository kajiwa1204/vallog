from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.repositories.summary import SummaryRepository
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
    return await summary_service.list_member_pr_summaries(db, project.id, login)
