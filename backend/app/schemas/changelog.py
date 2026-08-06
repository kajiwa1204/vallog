from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ChangeKind = Literal["pull_request", "issue", "review"]


class ChangeLogNotes(BaseModel):
    """エントリに添える事実注記。

    スコア・順位は載せない（docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
    ここに並ぶのは GitHub 上で確認できる事実だけで、解釈は読み手に委ねる。
    """

    # Issueに付いた SP ラベルの値。PR・レビューでは常に None
    story_points: int | None = None
    # PR: 作成から最初の他者レビューまでの時間 / レビュー: PR作成から自分の提出までの時間
    turnaround_hours: float | None = None
    # PR作者以外によるレビューが1件以上あるか。PRエントリでのみ意味を持つ
    reviewed_by_others: bool | None = None
    reopened_count: int = 0
    draft: bool = False


class ChangeLogEntry(BaseModel):
    kind: ChangeKind
    number: int
    title: str
    actor_login: str
    # 正規化済みの状態。PR: merged/open/closed、Issue: open/closed、
    # レビュー: approved/changes_requested/commented/dismissed（小文字）
    state: str
    occurred_at: datetime
    html_url: str
    notes: ChangeLogNotes


class ChangeLogResponse(BaseModel):
    entries: list[ChangeLogEntry]
