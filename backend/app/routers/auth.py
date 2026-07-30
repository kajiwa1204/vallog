import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import REFRESH_TOKEN_EXPIRE_DAYS
from app.schemas.user import TokenResponse, UserResponse
from app.services.auth import login_with_github_code, revoke_session, rotate_session

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_OAUTH_STATE_COOKIE = "github_oauth_state"
_OAUTH_STATE_MAX_AGE = 60 * 10
_REFRESH_MAX_AGE = 60 * 60 * 24 * REFRESH_TOKEN_EXPIRE_DAYS
_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_SCOPES = "read:user"


def _cookie_secure() -> bool:
    # localhost（開発環境）では secure=False にしないと Cookie が送信されない
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    return settings.frontend_url.startswith("https://")


def _set_auth_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=max_age,
        path=settings.auth_cookie_path,
    )


def _delete_auth_cookie(response: Response, key: str) -> None:
    # path は set 時と一致させないと削除されない
    response.delete_cookie(key=key, path=settings.auth_cookie_path)


def _drop_legacy_root_cookies(response: Response) -> None:
    """path を絞る前に発行した Path=/ の Cookie を掃除する。

    残っていると同名Cookieが2つ送られ、Starlette のパースは後勝ちなので古い方
    （Path=/）が読まれる。refresh では失効済みトークンとして再利用検知に当たり
    続けるため、30日間ログインが壊れる。全セッションが入れ替わったら削除してよい。
    """
    if settings.auth_cookie_path == "/":
        return
    for key in (_REFRESH_COOKIE, _OAUTH_STATE_COOKIE):
        response.delete_cookie(key=key, path="/")


@router.get("/github")
async def login_github():
    """GitHub OAuth 認証画面へリダイレクト"""
    state = secrets.token_urlsafe(32)
    url = f"{_GITHUB_AUTHORIZE_URL}?{urlencode({'client_id': settings.github_client_id, 'scope': _GITHUB_SCOPES, 'state': state})}"

    redirect = RedirectResponse(url)
    _set_auth_cookie(redirect, _OAUTH_STATE_COOKIE, state, _OAUTH_STATE_MAX_AGE)
    _drop_legacy_root_cookies(redirect)
    return redirect


@router.get("/github/callback")
async def github_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    expected_state: str | None = Cookie(default=None, alias=_OAUTH_STATE_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    """GitHub からのコールバック。code を検証してリフレッシュトークンを発行する。"""
    frontend_origin = settings.frontend_url.rstrip("/")

    def failure(reason: str) -> RedirectResponse:
        redirect = RedirectResponse(url=f"{frontend_origin}/?error={reason}")
        _delete_auth_cookie(redirect, _OAUTH_STATE_COOKIE)
        return redirect

    if error or code is None:
        return failure("auth_denied")

    # state を検証しないと、攻撃者が取得した code を踏ませて被害者のブラウザを
    # 攻撃者のアカウントでログインさせられる（ログインCSRF）。
    # compare_digest は str 同士だと両方ASCIIでないと TypeError になり、
    # 攻撃者が制御するクエリで未認証の500を作れてしまうため bytes で比較する
    if (
        state is None
        or expected_state is None
        or not secrets.compare_digest(state.encode("utf-8"), expected_state.encode("utf-8"))
    ):
        return failure("auth_state_mismatch")

    refresh_token = await login_with_github_code(db, code)

    redirect = RedirectResponse(url=f"{frontend_origin}/auth/callback")
    _delete_auth_cookie(redirect, _OAUTH_STATE_COOKIE)
    _set_auth_cookie(redirect, _REFRESH_COOKIE, refresh_token, _REFRESH_MAX_AGE)
    _drop_legacy_root_cookies(redirect)
    return redirect


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    """リフレッシュトークン（Cookie）から新しいアクセストークンを発行する。"""
    session = await rotate_session(db, refresh_token)
    _set_auth_cookie(response, _REFRESH_COOKIE, session.refresh_token, _REFRESH_MAX_AGE)
    _drop_legacy_root_cookies(response)
    return TokenResponse(
        access_token=session.access_token,
        user=UserResponse.model_validate(session.user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    """リフレッシュトークンを失効させて Cookie を削除する。"""
    await revoke_session(db, refresh_token)
    _delete_auth_cookie(response, _REFRESH_COOKIE)
    _drop_legacy_root_cookies(response)
