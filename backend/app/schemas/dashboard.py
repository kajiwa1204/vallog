from datetime import date, datetime

from pydantic import BaseModel


class PulseDay(BaseModel):
    """活動リズムの1日分。

    活動のない日も0で埋めて返す。歯抜けのまま返すとフロントが等間隔に並べたときに
    「静かだった日」が詰まって見え、リズムそのものが読めなくなる。
    """

    date: date
    pull_requests: int
    issues: int
    reviews: int


class AttentionPullRequest(BaseModel):
    number: int
    title: str
    author_login: str
    html_url: str
    opened_at: datetime
    # 作成から現在まで。「レビューが付くまで」ではなくまだ止まっている時間
    waiting_hours: float
    draft: bool


class AttentionIssue(BaseModel):
    number: int
    title: str
    html_url: str
    assignee_login: str
    assigned_at: datetime
    # 担当が付いてから現在まで
    stalled_hours: float


class Attention(BaseModel):
    """止まっているものだけを集める。

    ここに並ぶのは「誰かの評価」ではなく「チームが次に手を付ける先」で、
    件数が多いことは個人の落ち度を意味しない。
    """

    # OPEN・非draft・他者レビューなし
    review_wanted: list[AttentionPullRequest]
    # OPEN・draft。レビューを求めていないので review_wanted とは別に出す
    drafts: list[AttentionPullRequest]
    stalled_issues: list[AttentionIssue]


class Theme(BaseModel):
    """Issueラベル1種の集計。openとclosedを分けるのは「まだ動いている領域」を出すため。"""

    label: str
    open_count: int
    closed_count: int


class DashboardResponse(BaseModel):
    """チーム状況パネル3種（画面4）。

    スコアは含まない（docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
    3種はいずれも重み付けをせず、報酬の算定式には現れない。

    pulse / themes をベアなリストにしているのは、中身が1種類しかないものに空の
    ラッパーを噛ませないため。attention だけは3種の別リストを持つのでオブジェクトに
    している。
    """

    # いつ時点のキャッシュか。フロントはこれが null なら「初回同期中」と判断でき、
    # GET /projects/{id} の応答を待たずにローディング表現を決められる
    synced_at: datetime | None
    # 古い→新しい順
    pulse: list[PulseDay]
    attention: Attention
    # 合計（open + closed）降順
    themes: list[Theme]
