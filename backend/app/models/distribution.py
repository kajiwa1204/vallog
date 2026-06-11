import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DistributionProposal(Base):
    __tablename__ = "distribution_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    # 案ごとに重みを変えて比較できるよう、projectsとは別に重みを持つ
    weight_activity: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_speed: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_quality: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agreed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list["DistributionItem"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan", lazy="selectin"
    )
    edit_logs: Mapped[list["DistributionEditLog"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class DistributionItem(Base):
    __tablename__ = "distribution_items"
    __table_args__ = (UniqueConstraint("proposal_id", "github_login"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("distribution_proposals.id", ondelete="CASCADE"), nullable=False
    )
    # 未登録コントリビューターも扱えるよう、users.idではなくgithub_loginで管理する
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    # 分配比率（0〜1）。全アイテムの合計が1になるよう運用する
    ratio: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)

    proposal: Mapped["DistributionProposal"] = relationship(back_populates="items")


class DistributionEditLog(Base):
    __tablename__ = "distribution_edit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("distribution_proposals.id", ondelete="CASCADE"), nullable=False
    )
    edited_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 調整理由。UI側で入力必須。定性的な貢献の反映根拠を担保する
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # 変更前後のitemsまるごとのスナップショット。タイムライン表示を組みやすくするため
    before_items: Mapped[dict] = mapped_column(JSONB, nullable=False)
    after_items: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    proposal: Mapped["DistributionProposal"] = relationship(
        back_populates="edit_logs"
    )
    editor: Mapped["User"] = relationship()  # noqa: F821
