from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

# 片づいたものはPRのマージとIssueの完了だけ。レビューは「片づく」対象ではないので、
# changelog の ChangeKind（3値）は再利用しない
DoneKind = Literal["pull_request", "issue"]


class PulseDay(BaseModel):
    """活動リズムの1日分。

    活動のない日も0で埋めて返す。歯抜けのまま返すとフロントが等間隔に並べたときに
    「静かだった日」が詰まって見え、リズムそのものが読めなくなる。
    """

    date: date
    pull_requests: int
    issues: int
    reviews: int


class Pulse(BaseModel):
    """活動リズム。

    日次バケットに付随する値をここにまとめる。トップレベルに pulse_* を並べると
    付随情報が増えるたびに接頭辞付きのフィールドが生えていくため。

    total と previous_total をサーバが返すのは、フロントが days から復元すると
    「どの範囲を合計したか」の定義が2箇所に散るため。前期は days に含まれないので
    そもそも復元できない。
    """

    # 古い→新しい順
    days: list[PulseDay]
    total: int
    # 直前の同じ長さの期間の合計。単独の件数は多いとも少とも言えないため、
    # 読み手が基準を持てるように添える
    previous_total: int
    # サーバがどのオフセットで日付を畳んだか。フロントは変化ログの日付見出しを
    # ブラウザのローカル日付で作っており、基準がずれていないかを突き合わせられる
    # ようにエコーバックする
    tz_offset_minutes: int


class AttentionPullRequest(BaseModel):
    """レビューを待っているPR。

    タイムスタンプがあるのに経過時間も返すのは、足切り（REVIEW_WAITING_HOURS）が
    サーバ判定のため。表示とフィルタが同じ now を使っていないと、「24時間で切ったのに
    23.9時間と表示される」ような説明できないズレが出る。
    画面を開いたまま放置すると数字が固まるのは承知の上。
    """

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


class ChangesRequestedPullRequest(BaseModel):
    """修正を求められたまま動いていないPR。

    review_wanted とは待っている相手が逆で、こちらはPR作者の番。両者を同じリストに
    入れると「誰が次に動くのか」が読めなくなるため分ける。
    """

    number: int
    title: str
    author_login: str
    html_url: str
    # 最後に changes requested を出した人と、その時刻
    reviewer_login: str
    requested_at: datetime
    waiting_hours: float


class Attention(BaseModel):
    """止まっているものだけを集める。

    ここに並ぶのは「誰かの評価」ではなく「チームが次に手を付ける先」で、
    件数が多いことは個人の落ち度を意味しない。
    """

    # OPEN・非draft・他者レビューなし
    review_wanted: list[AttentionPullRequest]
    # OPEN・非draft・最終レビューが CHANGES_REQUESTED
    changes_requested: list[ChangesRequestedPullRequest]
    # OPEN・draft。レビューを求めていないので review_wanted とは別に出す
    drafts: list[AttentionPullRequest]
    stalled_issues: list[AttentionIssue]


class DoneItem(BaseModel):
    """片づいたもの1件（マージされたPR / 完了したIssue）。

    attention の裏返し。人ごとの件数には畳まない（畳むと「誰が多いか」の序列になり、
    ダッシュボードが出さないと決めた集約になる。docs/scoring_design.md）。
    """

    kind: DoneKind
    number: int
    title: str
    actor_login: str
    html_url: str
    occurred_at: datetime


class Theme(BaseModel):
    """Issueラベル1種の集計。openとclosedを分けるのは「まだ動いている領域」を出すため。"""

    label: str
    open_count: int
    closed_count: int
    # ラベル名の ":" より前（epic / priority など）。持たないラベルは None。
    # 「動いている領域」を読むには、領域を表すラベルとワークフロー用のラベルを
    # 混ぜずに並べる必要がある
    namespace: str | None = None


class Themes(BaseModel):
    """動いている領域。

    ラベルはリポジトリによって数百になりうるので、サーバで打ち切って total を添える。
    「17種のうち8種」と言えないと、画面は打ち切ったことすら伝えられない。

    attention には上限を置かない。あちらは詰まっている総量そのものが情報で、
    「10件で切りました」と言われても読み手にできることが無いため。
    """

    # 合計（open + closed）降順
    items: list[Theme]
    # 打ち切る前の種類数
    total: int


class DashboardResponse(BaseModel):
    """チーム状況パネル4種（画面4）。

    スコアは含まない（docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
    3種はいずれも重み付けをせず、報酬の算定式には現れない。

    recently_done だけベアなリストにしているのは、サーバが件数を決め打ちしていて
    「打ち切った」と言う必要が無いため（全部で6件、が仕様）。他は付随する値を持つので
    オブジェクトにしている。
    """

    # いつ時点のキャッシュか。フロントはこれが null なら「初回同期中」と判断でき、
    # GET /projects/{id} の応答を待たずにローディング表現を決められる
    synced_at: datetime | None
    # 変化ログを絞り込める顔ぶれ（大文字小文字を無視した辞書順）。
    #
    # サーバが返すのは、フロントが読み込み済みのエントリから作ると**取得件数に依存して
    # 顔ぶれが変わる**ため。既定の50件では直近に動いていない人がチップから消え、
    # その人の記録に辿り着けなくなっていた（#109）。サーバはキャッシュ全件を見るので
    # 件数に左右されず、Issueの担当しかしていない人（エントリの actor_login に
    # 現れない）も拾える。
    roster: list[str]
    pulse: Pulse
    attention: Attention
    # 新しい→古い順
    recently_done: list[DoneItem]
    themes: Themes
