import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, *, jti: uuid.UUID, user_id: uuid.UUID, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at)
        self._session.add(token)
        await self._session.commit()
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
        await self._session.commit()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self._session.commit()

    async def rotate(self, *, old_jti: uuid.UUID, user_id: uuid.UUID, expires_at: datetime) -> uuid.UUID:
        """旧トークンを失効させ、新トークンを1トランザクションで作成して返す。"""
        new_jti = uuid.uuid4()
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == old_jti)
            .values(revoked_at=datetime.now(timezone.utc))
        )
        self._session.add(RefreshToken(jti=new_jti, user_id=user_id, expires_at=expires_at))
        await self._session.commit()
        return new_jti
