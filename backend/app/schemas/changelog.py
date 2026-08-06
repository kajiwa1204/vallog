from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ChangeKind = Literal["pull_request", "issue", "review"]


class ChangeLogNotes(BaseModel):
    """エントリに添える事実注記。

    スコア・順位は載せない（docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
    ここに並ぶのは GitHub 上で確認できる事実だけで、解釈は読み手に委ねる。

    全フィールドが None 許容なのは「非適用」と「意味のあるゼロ」を区別するため。
    Issue行の reopened_count は「再オープンされていない(0)」ではなく「Issueに再オープンの
    概念を適用していない(None)」であり、0 を入れると事実として偽になる。適用外は None を
    返し、フロントは値の有無だけで表示を決められる（kind を見て握り潰す必要がない）。
    """

    # Issueに付いた SP ラベルの値。「獲得SP」ではなくラベルそのものの値で、
    # 未完了のIssueにも載る。完了分だけを見たい場合は state と併せて判断する
    story_points: int | None = None
    # PR行のみ: 作成から最初の他者レビューが付くまで（＝PR作者の待ち時間）
    first_review_hours: float | None = None
    # レビュー行のみ: PR作成から自分がレビューを出すまで（＝レビュアーの応答時間）。
    # first_review_hours と同じ区間を逆側から見た値で、読み手にとっての意味が正反対なため
    # 同名にはしない
    response_hours: float | None = None
    # PR行のみ: PR作者以外によるレビューが1件以上あるか
    reviewed_by_others: bool | None = None
    # PR行のみ
    reopened_count: int | None = None
    draft: bool | None = None


class ChangeLogEntry(BaseModel):
    # エントリの一意キー。number は kind をまたいで衝突する（PR #91 と、その
    # PRへのレビューはどちらも number=91）ため、一覧のキーには使えない。
    # 同一人物が同じPRに複数回レビューする場合もあるので、レビューは番号ではなく
    # レビュー自身のIDで識別する
    id: str
    kind: ChangeKind
    number: int
    title: str
    actor_login: str
    # 正規化済みの状態。PR: merged/open/closed、
    # Issue: open/closed/not_planned（却下・重複でのクローズを完了と区別する）、
    # レビュー: approved/changes_requested/commented/dismissed（小文字）
    state: str
    occurred_at: datetime
    html_url: str
    notes: ChangeLogNotes


class ChangeLogResponse(BaseModel):
    entries: list[ChangeLogEntry]
    # limit で打ち切られたか。ちょうど limit 件だった場合と区別が付かないと、
    # フロントは「もっと見る」を出すべきか判断できない
    has_more: bool = False
