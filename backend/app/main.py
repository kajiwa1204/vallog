from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, invitations, members, projects

app = FastAPI(
    title="vallog API",
    root_path=settings.fastapi_root_path,
)

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
app.include_router(invitations.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
