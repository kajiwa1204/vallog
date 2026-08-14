from fastapi import APIRouter, status

from app.repositories.project import ProjectRepository
from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.project import (
    CategoryWeights,
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdate,
    RepoOptionList,
)
from app.services import project as project_service

router = APIRouter(tags=["projects"])


def _to_response(project, member_count: int) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        repo_owner=project.repo_owner,
        repo_name=project.repo_name,
        weights=CategoryWeights(
            activity=project.weight_activity,
            speed=project.weight_speed,
            quality=project.weight_quality,
        ),
        member_count=member_count,
        github_synced_at=project.github_synced_at,
        created_at=project.created_at,
    )


@router.get("/projects", response_model=list[ProjectListItem])
async def list_projects(user: CurrentUser, db: DB):
    rows = await ProjectRepository(db).list_for_user(user.id)
    return [
        ProjectListItem(
            id=p.id,
            name=p.name,
            repo_owner=p.repo_owner,
            repo_name=p.repo_name,
            member_count=count,
        )
        for p, count in rows
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, user: CurrentUser, db: DB):
    project = await project_service.create_project(db, user, payload)
    return _to_response(project, member_count=1)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project: MemberProject, db: DB):
    count = await project_service.count_members(db, project.id)
    return _to_response(project, count)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(payload: ProjectUpdate, project: MemberProject, db: DB):
    project = await project_service.update_project(db, project, payload)
    count = await project_service.count_members(db, project.id)
    return _to_response(project, count)


@router.get("/github/repos", response_model=RepoOptionList)
async def list_github_repos(user: CurrentUser):
    """プロジェクト作成画面でリポジトリを選択するためのエンドポイント。"""
    return await project_service.list_selectable_repos(user)
