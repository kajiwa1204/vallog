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

    async def get_by_jti(self, jti: uuid.UUID, *, for_update: bool = False) -> RefreshToken | None:
        """for_update=True で行ロックを取る。

        ローテーション時に必要。素の SELECT だと READ COMMITTED では並行する
        2リクエストが揃って revoked_at IS NULL を読み、どちらも rotate に進む。
        後発の UPDATE は先行のコミット後に走るため、先行が作った子行が失効しない
        まま孤児として残り、1ユーザーに生きたチェーンが2本並走する。
        """
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
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
        """旧トークンを失効させ、新トークンを作成する。"""
        new_jti = uuid.uuid4()
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == old_jti)
            .values(revoked_at=datetime.now(timezone.utc))
        )
        self._session.add(RefreshToken(jti=new_jti, user_id=user_id, expires_at=expires_at))
        return new_jti

    async def delete_expired_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        """期限切れ行を削除する。失効済みでも期限内の行は再利用検知に必要なので残す。

        回収範囲は限定的で、これ単独ではゴミが残る。行が期限切れになるのは発行から
        30日後なので、使い続けているユーザーでは最初の30日間ずっと空振りのDELETEが
        毎リフレッシュ走る。逆に実際にゴミが溜まる「放置されたセッション」は
        rotate を呼ばないため永久に回収されない。現状の規模では許容している
        （定期ジョブ化は別Issue）。
        """
        await self._session.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.expires_at < now
            )
        )
