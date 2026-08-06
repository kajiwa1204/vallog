from typing import Annotated

from fastapi import APIRouter, Query

from app.routers.deps import DB, CurrentUser, MemberProject
from app.schemas.dashboard import DashboardResponse
from app.services import dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/projects/{project_id}/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    project: MemberProject,
    user: CurrentUser,
    db: DB,
    days: Annotated[int, Query(ge=1, le=90)] = dashboard.DEFAULT_PULSE_DAYS,
    # 閲覧者のUTCからのずれ（分・東が正）。日次バケットの日付境界に使う。
    # 未指定ならUTC基準。範囲はUTC-14:00〜UTC+14:00（実在するタイムゾーンの幅）
    tz_offset_minutes: Annotated[int, Query(ge=-840, le=840)] = 0,
):
    return await dashboard.get_dashboard(
        db,
        project,
        user.github_access_token,
        days=days,
        tz_offset_minutes=tz_offset_minutes,
    )
