import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.db.scalar(select(User).where(User.id == user_id))

    async def get_by_github_id(self, github_id: int) -> User | None:
        return await self.db.scalar(select(User).where(User.github_id == github_id))

    async def upsert_from_github(
        self,
        github_id: int,
        github_login: str,
        access_token: str,
        avatar_url: str | None,
    ) -> User:
        user = await self.get_by_github_id(github_id)
        if user is None:
            user = User(
                github_id=github_id,
                github_login=github_login,
                github_access_token=access_token,
                avatar_url=avatar_url,
            )
            self.db.add(user)
        else:
            user.github_login = github_login
            user.github_access_token = access_token
            user.avatar_url = avatar_url
        await self.db.flush()
        return user
