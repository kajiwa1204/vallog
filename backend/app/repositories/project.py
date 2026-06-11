import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import InvitationLink, Project, ProjectMember, User


class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, project_id: uuid.UUID) -> Project | None:
        return await self.db.scalar(
            select(Project).where(Project.id == project_id)
        )

    async def get_by_repo(self, owner: str, name: str) -> Project | None:
        return await self.db.scalar(
            select(Project).where(
                Project.repo_owner == owner, Project.repo_name == name
            )
        )

    async def list_for_user(self, user_id: uuid.UUID) -> list[tuple[Project, int]]:
        """ユーザーが参加中のプロジェクトと、各メンバー数を返す。"""
        member_count = (
            select(func.count())
            .select_from(ProjectMember)
            .where(ProjectMember.project_id == Project.id)
            .scalar_subquery()
        )
        rows = await self.db.execute(
            select(Project, member_count)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
        return [(p, c) for p, c in rows.all()]

    async def count_members(self, project_id: uuid.UUID) -> int:
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(ProjectMember)
                .where(ProjectMember.project_id == project_id)
            )
        ) or 0

    async def create(self, project: Project) -> Project:
        self.db.add(project)
        await self.db.flush()
        return project

    async def is_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        row = await self.db.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        return row is not None

    async def add_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        if not await self.is_member(project_id, user_id):
            self.db.add(ProjectMember(project_id=project_id, user_id=user_id))
            await self.db.flush()

    async def list_member_users(self, project_id: uuid.UUID) -> list[User]:
        rows = await self.db.scalars(
            select(User)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_id)
        )
        return list(rows.all())

    async def lock_for_sync(self, project_id: uuid.UUID) -> Project | None:
        """スタンピード対策: 行ロックを取って同期フラグを原子的に確認・更新する。"""
        return await self.db.scalar(
            select(Project).where(Project.id == project_id).with_for_update()
        )

    async def create_invitation(self, invitation: InvitationLink) -> InvitationLink:
        self.db.add(invitation)
        await self.db.flush()
        return invitation

    async def get_invitation(self, token: str) -> InvitationLink | None:
        return await self.db.scalar(
            select(InvitationLink)
            .where(InvitationLink.token == token)
            .options(selectinload(InvitationLink.project))
        )

    async def get_active_invitation(
        self, project_id: uuid.UUID, now: datetime
    ) -> InvitationLink | None:
        return await self.db.scalar(
            select(InvitationLink)
            .where(
                InvitationLink.project_id == project_id,
                InvitationLink.expires_at > now,
            )
            .order_by(InvitationLink.created_at.desc())
            .limit(1)
        )
