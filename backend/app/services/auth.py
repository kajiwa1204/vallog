import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.security import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository

_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"

# ローテーション直後は、Cookieを共有する複数タブが同じ旧トークンを送りうる。
# この猶予期間内の再送は攻撃ではなく正常系として後継トークンを返す。
REFRESH_ROTATION_GRACE = timedelta(seconds=30)


async def fetch_github_access_token(code: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                _GITHUB_TOKEN_URL,
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
        data = res.json()
    except httpx.TimeoutException as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_TIMEOUT,
            "Connection to GitHub timed out",
        ) from e
    except (httpx.HTTPError, ValueError) as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_UNAVAILABLE,
            "Failed to connect to GitHub",
        ) from e

    token = data.get("access_token")
    if not token:
        error = data.get("error") or "unknown_error"
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            ErrorCode.GITHUB_TOKEN_EXCHANGE_FAILED,
            f"Failed to obtain GitHub access token: {error}",
        )
    return token


async def fetch_github_user(access_token: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                _GITHUB_USER_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if res.status_code != 200:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                ErrorCode.GITHUB_USER_FETCH_FAILED,
                "Failed to fetch GitHub user info",
            )
        return res.json()
    except httpx.TimeoutException as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_TIMEOUT,
            "Connection to GitHub timed out",
        ) from e
    except httpx.HTTPError as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_UNAVAILABLE,
            "Failed to connect to GitHub",
        ) from e
    except ValueError as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_INVALID_RESPONSE,
            "Received an invalid response from GitHub",
        ) from e


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    user: User


def _refresh_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def _invalid_token() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_INVALID_TOKEN, "Invalid token")


async def _load_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_USER_NOT_FOUND, "User not found"
        )
    return user


async def login_with_github_code(db: AsyncSession, code: str) -> str:
    """認可コードをユーザーに紐づけ、発行したリフレッシュトークンを返す。"""
    github_token = await fetch_github_access_token(code)
    github_user = await fetch_github_user(github_token)

    user = await UserRepository(db).upsert(
        github_id=github_user["id"],
        github_login=github_user["login"],
        github_access_token=github_token,
        avatar_url=github_user.get("avatar_url"),
    )

    jti = uuid.uuid4()
    await RefreshTokenRepository(db).create(
        jti=jti, user_id=user.id, expires_at=_refresh_expires_at()
    )
    await db.commit()
    return create_refresh_token(user.id, jti)


async def rotate_session(db: AsyncSession, refresh_token: str | None) -> AuthSession:
    """リフレッシュトークンを検証し、ローテーションして新しいセッションを返す。"""
    if refresh_token is None:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.AUTH_REFRESH_TOKEN_MISSING,
            "Missing refresh token",
        )

    user_id, jti = decode_refresh_token(refresh_token)
    repo = RefreshTokenRepository(db)
    stored = await repo.get_by_jti(jti)
    if stored is None:
        raise _invalid_token()

    now = datetime.now(timezone.utc)
    # JWTの exp とは別に、DB側でも期限を持つ（DB側だけ短縮する運用を可能にするため）
    if stored.expires_at <= now:
        raise _invalid_token()

    if stored.revoked_at is not None:
        return await _reissue_within_grace(db, repo, stored, now)

    user = await _load_user(db, user_id)
    new_jti = await repo.rotate(
        old_jti=jti, user_id=user_id, expires_at=_refresh_expires_at()
    )
    await repo.delete_expired_for_user(user_id, now)
    await db.commit()

    return AuthSession(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id, new_jti),
        user=user,
    )


async def _reissue_within_grace(
    db: AsyncSession,
    repo: RefreshTokenRepository,
    stored: RefreshToken,
    now: datetime,
) -> AuthSession:
    """失効済みトークンの再送を、並行リクエストと真の再利用に切り分ける。"""
    child = None
    if stored.replaced_by_jti is not None and now - stored.revoked_at <= REFRESH_ROTATION_GRACE:
        child = await repo.get_by_jti(stored.replaced_by_jti)

    # 後継がない・後継も失効済み（＝さらに世代が進んだ後の再送）なら盗用と見なす
    if child is None or child.revoked_at is not None or child.expires_at <= now:
        await repo.revoke_all_for_user(stored.user_id)
        await db.commit()
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.AUTH_TOKEN_REUSE_DETECTED,
            "Token reuse detected",
        )

    # 猶予期間内なので再ローテーションはせず、後継トークンをそのまま再発行する
    return AuthSession(
        access_token=create_access_token(stored.user_id),
        refresh_token=create_refresh_token(stored.user_id, child.jti),
        user=await _load_user(db, stored.user_id),
    )


async def revoke_session(db: AsyncSession, refresh_token: str | None) -> None:
    """リフレッシュトークンを失効させる。不正・期限切れでもログアウトは成功させる。"""
    if refresh_token is None:
        return
    try:
        _, jti = decode_refresh_token(refresh_token)
    except AppError:
        return
    await RefreshTokenRepository(db).revoke(jti)
    await db.commit()
