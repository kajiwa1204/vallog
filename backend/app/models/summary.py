import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SummaryJob(Base):
    __tablename__ = "summary_jobs"
    __table_args__ = (
        Index("ix_summary_jobs_project_login", "project_id", "github_login"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    # pending | running | succeeded | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    total_prs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done_prs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # NULL=メンバー一括ジョブ、非NULL=そのPR単独のジョブ
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ContributionSummary(Base):
    __tablename__ = "contribution_summaries"
    __table_args__ = (UniqueConstraint("project_id", "github_login"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 生成に使ったGitHubデータのハッシュ。データが変わった場合のみ再生成する
    context_hash: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PRSummary(Base):
    __tablename__ = "pr_summaries"
    __table_args__ = (
        UniqueConstraint("project_id", "pr_number"),
        # メンバーサマリー生成時にauthor単位で絞り込むためのインデックス
        Index("ix_pr_summaries_project_author", "project_id", "author_login"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    author_login: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 生成に使ったPR+レビューデータのハッシュ。マージ済みPRは不変なので再課金されない
    context_hash: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
