import uuid

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.security import (
    REFRESH_TOKEN_EXPIRE,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.repositories.user import UserRepository
from app.routers.deps import DB, CurrentUser
from app.schemas.user import TokenResponse, UserResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "vallog_refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int(REFRESH_TOKEN_EXPIRE.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.frontend_url.startswith("https"),
        path="/api/auth",
    )


@router.get("/github/login")
async def github_login(invite: str | None = None):
    return RedirectResponse(auth_service.build_authorize_url(invite))


@router.get("/github/callback")
async def github_callback(code: str, state: str, db: DB):
    user, redirect_path = await auth_service.handle_callback(db, code, state)
    response = RedirectResponse(f"{settings.frontend_url}{redirect_path}")
    _set_refresh_cookie(response, create_refresh_token(user.id))
    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: DB,
    vallog_refresh_token: str | None = Cookie(default=None),
):
    if vallog_refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    claims = decode_token(vallog_refresh_token, "refresh")
    user = await UserRepository(db).get(uuid.UUID(claims["sub"]))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    # ローテーションして有効期限を延長する
    _set_refresh_cookie(response, create_refresh_token(user.id))
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser):
    return UserResponse.model_validate(user)
