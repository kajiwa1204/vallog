import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import TypeDecorator

from app.core.config import settings
from app.core.database import get_db

ACCESS_TOKEN_EXPIRE = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRE = timedelta(days=30)
OAUTH_STATE_EXPIRE = timedelta(minutes=10)

_ALGORITHM = "HS256"


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


def _create_token(payload: dict[str, Any], token_type: str, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    claims = {**payload, "type": token_type, "iat": now, "exp": now + expires}
    return jwt.encode(claims, settings.jwt_secret, algorithm=_ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token({"sub": str(user_id)}, "access", ACCESS_TOKEN_EXPIRE)


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token({"sub": str(user_id)}, "refresh", REFRESH_TOKEN_EXPIRE)


def create_oauth_state_token(payload: dict[str, Any]) -> str:
    """OAuth開始時のCSRF対策 + 招待トークンの引き回しに使う署名付きstate。"""
    return _create_token(payload, "oauth_state", OAUTH_STATE_EXPIRE)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    if claims.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    return claims


_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models import User

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    claims = decode_token(credentials.credentials, "access")
    user = await db.scalar(select(User).where(User.id == uuid.UUID(claims["sub"])))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
