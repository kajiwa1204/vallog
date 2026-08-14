from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import AppError, app_error_handler
from app.routers import (
    auth,
    changelog,
    dashboard,
    distribution,
    invitations,
    members,
    projects,
    scores,
    summaries,
)

app = FastAPI(
    title="vallog API",
    root_path=settings.fastapi_root_path,
)

app.add_exception_handler(AppError, app_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(members.router)
app.include_router(scores.router)
app.include_router(changelog.router)
app.include_router(dashboard.router)
app.include_router(invitations.router)
app.include_router(summaries.router)
app.include_router(distribution.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
