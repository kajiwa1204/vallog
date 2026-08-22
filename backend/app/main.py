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


def api_docs_enabled() -> bool:
    """APIドキュメントを公開してよいか。

    未指定なら FRONTEND_URL のスキームで判断する。localhost（http）の開発では
    開き、公開環境（https）では閉じる、が既定の振る舞い。
    """
    if settings.expose_api_docs is not None:
        return settings.expose_api_docs
    return not settings.frontend_url.startswith("https://")


_docs = api_docs_enabled()

app = FastAPI(
    title="vallog API",
    root_path=settings.fastapi_root_path,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
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
