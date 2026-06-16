from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token
from app.repositories.user import UserRepository
from app.schemas.user import UserResponse
from app.services.auth import fetch_github_access_token, fetch_github_user

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_SCOPES = "read:user,repo"


def _set_refresh_cookie(response: Response, token: str) -> None:
    # localhost（開発環境）では secure=False にしないと Cookie が送信されない
    secure = settings.frontend_url.startswith("https://")
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )


@router.get("/github")
async def login_github():
    """GitHub OAuth 認証画面へリダイレクト"""
    url = (
        f"{_GITHUB_AUTHORIZE_URL}"
        f"?client_id={settings.github_client_id}"
        f"&scope={_GITHUB_SCOPES}"
    )
    return RedirectResponse(url)


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

    repo = UserRepository(db)
    user = await repo.upsert(
        github_id=github_user["id"],
        github_login=github_user["login"],
        github_access_token=github_token,
        avatar_url=github_user.get("avatar_url"),
    )

    refresh_token = create_refresh_token(user.id)
    redirect = RedirectResponse(url=f"{frontend_origin}/auth/callback")
    _set_refresh_cookie(redirect, refresh_token)
    return redirect


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    """リフレッシュトークン（Cookie）から新しいアクセストークンを発行する。"""
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="リフレッシュトークンがありません",
        )
    user_id = decode_refresh_token(refresh_token)
    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)
    _set_refresh_cookie(response, new_refresh_token)
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """リフレッシュトークンの Cookie を削除する。"""
    response.delete_cookie(key=_REFRESH_COOKIE)
