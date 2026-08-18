import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.project import CategoryWeights


class DistributionItemInput(BaseModel):
    # 未登録の貢献者も分配対象にできるのは意図的な仕様（ItemsUpdate 参照）なので
    # プロジェクトメンバーには縛らない。ただしGitHubのログイン規則（39文字以内・
    # 英数字とハイフン）は安定した契約なので、DBと画面に任意の文字列が流れ込むのは
    # ここで止める。「ハイフン連続不可・先頭末尾ハイフン不可」までは見ない —
    # 厳しくしすぎると、GitHub側の規則が緩んだときに正当なログインを弾く
    github_login: str = Field(min_length=1, max_length=39, pattern=r"^[A-Za-z0-9-]+$")
    ratio: Decimal = Field(ge=0, le=1)


def _reject_duplicate_logins(items: list[DistributionItemInput]) -> None:
    logins = [i.github_login for i in items]
    duplicates = sorted({login for login in logins if logins.count(login) > 1})
    if duplicates:
        raise ValueError(f"Duplicate github_login: {', '.join(duplicates)}")


class ProposalCreate(BaseModel):
    name: str | None = None
    # 省略時はプロジェクトのデフォルト重みを使う
    weights: CategoryWeights | None = None
    total_amount: Decimal | None = Field(default=None, ge=0)
    # 省略時はスコアから初期分配比率を算出する。既存案の複製など、
    # クライアントが比率を決めている場合のみ明示的に渡す
    items: list[DistributionItemInput] | None = Field(default=None, min_length=1)

    @field_validator("items")
    @classmethod
    def items_must_be_unique(
        cls, v: list[DistributionItemInput] | None
    ) -> list[DistributionItemInput] | None:
        if v is not None:
            _reject_duplicate_logins(v)
        return v


class ItemsUpdate(BaseModel):
    """手動調整のリクエスト。理由は必須（画面7「調整時に理由の入力を必須とする」）。

    items は案の配分値そのものを置き換える。ここに無いメンバーは案から外れ、
    新しいログインを足せば分配対象に加わる。
    """

    reason: str
    items: list[DistributionItemInput] = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Reason is required")
        return stripped

    @model_validator(mode="after")
    def items_must_be_unique(self) -> "ItemsUpdate":
        _reject_duplicate_logins(self.items)
        return self


class ProposalUpdate(BaseModel):
    """案そのものの更新。重みを変えた場合は分配比率をスコアから再計算する。"""

    reason: str
    name: str | None = None
    total_amount: Decimal | None = Field(default=None, ge=0)
    weights: CategoryWeights | None = None

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Reason is required")
        return stripped

    @model_validator(mode="after")
    def at_least_one_change(self) -> "ProposalUpdate":
        if self.name is None and self.total_amount is None and self.weights is None:
            raise ValueError("At least one of name, total_amount, weights is required")
        return self


class DistributionItemResponse(BaseModel):
    github_login: str
    # Vallog未登録の貢献者はNULL。フロントはGitHubのidenticonにフォールバックする
    avatar_url: str | None = None
    ratio: Decimal
    # 報酬総額が入力されていれば按分した金額。未入力ならNULL
    amount: Decimal | None = None


class SnapshotItem(BaseModel):
    github_login: str
    ratio: Decimal


class ProposalSnapshot(BaseModel):
    """編集ログに残す案の状態。"""

    items: list[SnapshotItem]
    total_amount: Decimal | None
    weights: CategoryWeights


class EditLogResponse(BaseModel):
    id: uuid.UUID
    # 編集者が退会済みならNULL
    edited_by_github_login: str | None
    edited_by_avatar_url: str | None
    reason: str
    before_items: ProposalSnapshot
    after_items: ProposalSnapshot
    created_at: datetime


class ProposalListItem(BaseModel):
    id: uuid.UUID
    name: str
    total_amount: Decimal | None
    finalized: bool
    finalized_at: datetime | None
    # 「誰が確定したか」は合意の記録の一部。作成者とは別人になりうるので両方返す
    finalized_by_github_login: str | None
    created_by_github_login: str | None
    created_at: datetime
    # 削除済みなら値が入る。物理削除しないのは #100 の抑止が痕跡の存在に依存するため
    deleted_at: datetime | None = None
    deleted_by_github_login: str | None = None


class ProposalResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    weights: CategoryWeights
    total_amount: Decimal | None
    finalized: bool
    finalized_at: datetime | None
    finalized_by_github_login: str | None
    created_by_github_login: str | None
    created_at: datetime
    items: list[DistributionItemResponse]
    edit_logs: list[EditLogResponse]
