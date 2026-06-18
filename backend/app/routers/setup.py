from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.routers.deps import DB
from app.schemas.setup import SetupGitHubRequest, SetupStatusResponse
from app.services.app_credentials import is_configured, save_github_credentials

router = APIRouter(prefix="/setup", tags=["setup"])

# フロントエンドのOAuthコールバックパス（routers/auth.py の callback と合わせる）
_CALLBACK_PATH = "/api/auth/github/callback"


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(db: DB) -> SetupStatusResponse:
    configured = await is_configured(db)
    return SetupStatusResponse(
        configured=configured,
        callback_url=f"{settings.frontend_url}{_CALLBACK_PATH}",
    )


@router.post("/github", status_code=status.HTTP_204_NO_CONTENT)
async def post_setup_github(body: SetupGitHubRequest, db: DB) -> None:
    if await is_configured(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="GitHub OAuthはすでに設定済みです。",
        )
    await save_github_credentials(db, body.client_id, body.client_secret)
