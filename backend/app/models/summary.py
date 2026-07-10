import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PRSummary(Base):
    """Tier 1: PRごとの貢献サマリー。

    マージ済みPRは内容が不変なので、一度生成すれば再課金されない。
    """

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
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    author_login: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 生成に使ったPR+レビューデータのハッシュ。head_shaの変化でdiffの変化を検知する
    context_hash: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ContributionSummary(Base):
    """Tier 2: メンバー単位の貢献サマリー。Tier 1集合 + Issue/Review実績から生成する。"""

    __tablename__ = "contribution_summaries"
    __table_args__ = (UniqueConstraint("project_id", "github_login"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Tier 1サマリーの内容が変わった場合のみ再生成する
    context_hash: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SummaryJob(Base):
    """サマリー生成のバックグラウンドジョブ。フロントは進捗をポーリングする。"""

    __tablename__ = "summary_jobs"
    __table_args__ = (
        Index("ix_summary_jobs_project_login", "project_id", "github_login"),
        # 同一メンバー/PRのアクティブ(pending/running)ジョブの二重起動をDBで防ぐ。
        # メンバー一括(pr_number IS NULL)とPR単独(pr_number IS NOT NULL)でスコープが
        # 異なるため部分ユニークインデックスを2本張る。
        Index(
            "uq_summary_jobs_active_member",
            "project_id",
            "github_login",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running') AND pr_number IS NULL"),
        ),
        Index(
            "uq_summary_jobs_active_pr",
            "project_id",
            "github_login",
            "pr_number",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running') AND pr_number IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
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
