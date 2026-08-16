import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
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
    """分配シミュレーションの1案。

    重みを案ごとに持つのは、同じGitHubデータに別の重みを当てた複数案を並べて比較する
    ためで、`projects` のデフォルト重みとは別物（docs/data_model.md「カテゴリ重みを
    projects と distribution_proposals の両方に持つ」）。
    """

    __tablename__ = "distribution_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    weight_activity: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_speed: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_quality: Mapped[int] = mapped_column(Integer, nullable=False)
    # 報酬総額。未入力なら分配比率だけを表示する（画面7「報酬総額の入力: 任意入力」）。
    # 金額は誤差が許されないためfloatではなくNumericで持つ
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 合意の記録は退会後も残す必要があるため、ユーザー削除ではNULLにするだけにする
    finalized_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 削除は物理削除にしない。#100 の抑止は「created_by が記録され編集履歴が全員に
    # 公開される」ことで成り立っているので、行ごと消せると「案を作ってスコアを読み、
    # 削除する」で痕跡がゼロになり、抑止の根拠自体が無くなる
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    items: Mapped[list["DistributionItem"]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="DistributionItem.github_login",
    )
    # タイムラインは新しい編集から読むため降順で返す
    edit_logs: Mapped[list["DistributionEditLog"]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="DistributionEditLog.created_at.desc()",
    )
    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])  # noqa: F821
    finalizer: Mapped["User | None"] = relationship(foreign_keys=[finalized_by])  # noqa: F821
    deleter: Mapped["User | None"] = relationship(foreign_keys=[deleted_by])  # noqa: F821


class DistributionItem(Base):
    """分配案のメンバー別配分値。

    未登録の貢献者も分配対象になりうるため、`users.id` ではなくGitHubログインで持つ
    （docs/data_model.md「github_login を user_id の代わりに使う」）。
    """

    __tablename__ = "distribution_items"
    __table_args__ = (UniqueConstraint("proposal_id", "github_login"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("distribution_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    # 0〜1の分配比率。合計が正確に1になることを保つため、金額と同じくNumericで持つ
    ratio: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)

    proposal: Mapped["DistributionProposal"] = relationship(back_populates="items")


class DistributionEditLog(Base):
    """分配案の編集履歴。全員に公開して不正操作への社会的抑止力とする（承認制は不採用）。

    カラム単位の差分ではなく変更前後の配分値をまるごとJSONBで持つ。フロントの
    タイムライン表示がログ1件だけで完結し、過去の状態を再構築せずに済むため
    （docs/data_model.md「distribution_edit_logs はJSONBスナップショット」）。
    """

    __tablename__ = "distribution_edit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("distribution_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 編集者が退会してもログは残す（誰がいつ何をしたかの記録が抑止力の根拠のため）
    edited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # 定性的な貢献の反映根拠。UI・APIともに入力必須
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # {"items": [...], "total_amount": ..., "weights": {...}}。重み変更・総額変更も
    # 比率と同じタイムラインに出せるよう、案の状態をまとめて持つ
    before_items: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    after_items: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    proposal: Mapped["DistributionProposal"] = relationship(back_populates="edit_logs")
    editor: Mapped["User | None"] = relationship()  # noqa: F821
