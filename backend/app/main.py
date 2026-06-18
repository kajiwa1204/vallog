from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.summary import SummaryJob
from app.routers import (
    auth,
    distribution,
    invitations,
    members,
    projects,
    scores,
    setup,
    summaries,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 再起動でタスクが消えた pending/running ジョブを failed に更新する
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(SummaryJob)
            .where(SummaryJob.status.in_(["pending", "running"]))
            .values(
                status="failed",
                error="サーバ再起動により中断されました",
                finished_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
    yield


app = FastAPI(
    title="vallog API",
    root_path=settings.fastapi_root_path,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(setup.router)
app.include_router(projects.router)
app.include_router(members.router)
app.include_router(scores.router)
app.include_router(distribution.router)
app.include_router(summaries.router)
app.include_router(invitations.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
