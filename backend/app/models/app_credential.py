import uuid

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppCredential(Base):
    """インスタンス全体のGitHub OAuth資格情報を1行だけ保存するテーブル。"""

    __tablename__ = "app_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    github_client_id: Mapped[str] = mapped_column(String, nullable=False)
    # Fernet暗号化済みのclient_secret。APIレスポンスとして返してはならない
    github_client_secret_encrypted: Mapped[str] = mapped_column(
        String, nullable=False
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
