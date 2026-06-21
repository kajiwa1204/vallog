import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_github_id(self, github_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.github_id == github_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        github_id: int,
        github_login: str,
        github_access_token: str,
        avatar_url: str | None,
    ) -> User:
        user = await self.get_by_github_id(github_id)
        if user is None:
            user = User(
                github_id=github_id,
                github_login=github_login,
                github_access_token=github_access_token,
                avatar_url=avatar_url,
            )
            self._session.add(user)
        else:
            user.github_login = github_login
            user.github_access_token = github_access_token
            user.avatar_url = avatar_url

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            user = await self.get_by_github_id(github_id)
            if user is None:
                raise
            user.github_login = github_login
            user.github_access_token = github_access_token
            user.avatar_url = avatar_url
            await self._session.commit()

        await self._session.refresh(user)
        return user
