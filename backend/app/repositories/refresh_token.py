import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    """コミットは呼び出し側（services/auth.py）がトランザクション境界として行う。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, *, jti: uuid.UUID, user_id: uuid.UUID, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at)
        self._session.add(token)
        return token

    async def get_by_jti(self, jti: uuid.UUID) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.scalar_one_or_none()

    async def revoke(self, jti: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == jti)
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def rotate(self, *, old_jti: uuid.UUID, user_id: uuid.UUID, expires_at: datetime) -> uuid.UUID:
        """旧トークンを失効させ、後継への参照を残して新トークンを作成する。"""
        new_jti = uuid.uuid4()
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == old_jti)
            .values(revoked_at=datetime.now(timezone.utc), replaced_by_jti=new_jti)
        )
        self._session.add(RefreshToken(jti=new_jti, user_id=user_id, expires_at=expires_at))
        return new_jti

    async def delete_expired_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        """期限切れ行を削除する。失効済みでも期限内の行は再利用検知に必要なので残す。"""
        await self._session.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.expires_at < now
            )
        )
