import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.services.auth import fetch_github_access_token, fetch_github_user

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_OAUTH_STATE_COOKIE = "github_oauth_state"
_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_SCOPES = "read:user"


def _refresh_token_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def _set_refresh_cookie(response: Response, token: str) -> None:
    # localhost（開発環境）では secure=False にしないと Cookie が送信されない
    secure = settings.frontend_url.startswith("https://")
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=60 * 60 * 24 * REFRESH_TOKEN_EXPIRE_DAYS,
    )


@router.get("/github")
async def login_github():
    """GitHub OAuth 認証画面へリダイレクト"""
    state = secrets.token_urlsafe(32)
    url = f"{_GITHUB_AUTHORIZE_URL}?{urlencode({'client_id': settings.github_client_id, 'scope': _GITHUB_SCOPES, 'state': state})}"

    redirect = RedirectResponse(url)
    secure = settings.frontend_url.startswith("https://")
    redirect.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=60 * 10,
    )
    return redirect


@router.get("/github/callback")
async def github_callback(
    code: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """GitHub からのコールバック。code を受け取り JWT を発行してフロントへリダイレクト。"""
    frontend_origin = settings.frontend_url.rstrip("/")

    if error or code is None:
        return RedirectResponse(url=f"{frontend_origin}/?error=auth_denied")

    github_token = await fetch_github_access_token(code)
    github_user = await fetch_github_user(github_token)

    user = await UserRepository(db).upsert(
        github_id=github_user["id"],
        github_login=github_user["login"],
        github_access_token=github_token,
        avatar_url=github_user.get("avatar_url"),
    )

    jti = uuid.uuid4()
    refresh_token = create_refresh_token(user.id, jti)
    await RefreshTokenRepository(db).create(
        jti=jti,
        user_id=user.id,
        expires_at=_refresh_token_expires_at(),
    )

    redirect = RedirectResponse(url=f"{frontend_origin}/auth/callback")
    redirect.delete_cookie(key=_OAUTH_STATE_COOKIE)
    _set_refresh_cookie(redirect, refresh_token)
    return redirect


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    """リフレッシュトークン（Cookie）から新しいアクセストークンを発行する。"""
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="リフレッシュトークンがありません",
        )

    user_id, jti = decode_refresh_token(refresh_token)

    repo = RefreshTokenRepository(db)
    stored = await repo.get_by_jti(jti)

    if stored is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if stored.revoked_at is not None:
        # 失効済みトークンの再利用 → このユーザーの全トークンを無効化
        await repo.revoke_all_for_user(user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token reuse detected",
        )

    new_jti = await repo.rotate(
        old_jti=jti,
        user_id=user_id,
        expires_at=_refresh_token_expires_at(),
    )

    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id, new_jti)
    _set_refresh_cookie(response, new_refresh_token)
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    """リフレッシュトークンを失効させて Cookie を削除する。"""
    if refresh_token is not None:
        try:
            _, jti = decode_refresh_token(refresh_token)
            await RefreshTokenRepository(db).revoke(jti)
        except HTTPException:
            pass  # 期限切れ・不正なトークンでもログアウト自体は成功させる
    response.delete_cookie(key=_REFRESH_COOKIE)
