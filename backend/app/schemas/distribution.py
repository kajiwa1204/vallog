import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.project import CategoryWeights


class ProposalCreate(BaseModel):
    title: str
    total_amount: Decimal | None = None


class ItemUpdate(BaseModel):
    github_login: str
    ratio: Decimal = Field(ge=0, le=1)


class ProposalUpdate(BaseModel):
    """変更には理由の入力を必須とし、編集履歴として全員に公開する。"""

    reason: str = Field(min_length=1)
    title: str | None = None
    total_amount: Decimal | None = None
    # 重みを変えた場合はスコアから分配比率を再計算する
    weights: CategoryWeights | None = None
    # 手動調整。指定した場合はこの値で上書きする
    items: list[ItemUpdate] | None = None


class ItemResponse(BaseModel):
    github_login: str
    avatar_url: str | None
    ratio: Decimal
    amount: Decimal | None


class ProposalResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    total_amount: Decimal | None
    weights: CategoryWeights
    items: list[ItemResponse]
    creator_login: str
    created_at: datetime
    agreed_at: datetime | None


class ProposalListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    total_amount: Decimal | None
    creator_login: str
    created_at: datetime
    agreed_at: datetime | None


class EditLogResponse(BaseModel):
    id: uuid.UUID
    editor_login: str
    editor_avatar_url: str | None
    reason: str
    before_items: dict
    after_items: dict
    created_at: datetime
