import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from cryptography.fernet import Fernet
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import TypeDecorator

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ErrorCode

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

_bearer = HTTPBearer(auto_error=False)


class EncryptedString(TypeDecorator):
    """DBに暗号化して保存するString型。読み書き時に自動で暗号化/復号する。"""

    impl = String
    cache_ok = True

    def _fernet(self) -> Fernet:
        return Fernet(settings.encryption_key.encode())

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self._fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self._fernet().decrypt(value.encode()).decode()


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": expire},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: uuid.UUID, jti: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "type": "refresh", "jti": str(jti), "exp": expire},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def _decode_token(token: str, expected_type: str) -> tuple[uuid.UUID, dict]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_INVALID_TOKEN, "Invalid token")
    if payload.get("type") != expected_type:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_INVALID_TOKEN, "Invalid token")
    sub = payload.get("sub")
    if sub is None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_INVALID_TOKEN, "Invalid token")
    try:
        return (uuid.UUID(sub), payload)
    except ValueError:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_INVALID_TOKEN, "Invalid token")


def decode_access_token(token: str) -> uuid.UUID:
    user_id, _ = _decode_token(token, "access")
    return user_id


def decode_refresh_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (user_id, jti)"""
    user_id, payload = _decode_token(token, "refresh")
    jti_str = payload.get("jti")
    if jti_str is None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_INVALID_TOKEN, "Invalid token")
    try:
        return user_id, uuid.UUID(jti_str)
    except ValueError:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_INVALID_TOKEN, "Invalid token")


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    if credentials is None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_NOT_AUTHENTICATED, "Not authenticated")
    return decode_access_token(credentials.credentials)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.user import User

    if credentials is None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_NOT_AUTHENTICATED, "Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTH_USER_NOT_FOUND, "User not found")
    return user
