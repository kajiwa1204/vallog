from pydantic import BaseModel

from app.schemas.project import CategoryWeights


class CategoryScores(BaseModel):
    """カテゴリごとの相対スコア。各カテゴリはメンバー間で合計1.0（誰も値を持たなければ0.0）。"""

    activity: float
    speed: float
    quality: float


class MemberFacts(BaseModel):
    """スコアに潰す前の生事実。正規化も重み付けもしない実数（画面7の「レシート」用）。

    **フィールド名で母集合を言い切る。** 同じ「SP」でも、スコアはSPを担当者にのみ配る一方、
    変化ログの絞り込みはIssueだけ起票者∪担当者なので、母集合を書かずに数字を並べると
    分配の席で数が合わない。名前に含めておけば画面のラベルもそこから外れない。

    値はスコア計算が使っているのと同じ関数から取る。別に数え直すと、除外条件
    （bot・unknown・セルフレビュー・成果でないクローズ）が片方だけ直された日に、
    同じ画面で「スコアの根拠」と「並んでいる事実」が食い違う。
    """

    # 担当した完了Issueで獲得したSPの合計。起票しただけのIssueは入らない
    story_points_earned: int
    # 自分が作成したPRの件数。Issueの起票は含まない
    pull_requests_authored: int
    # 自分が出したレビューの件数。自分のPRへのセルフレビューは除く
    reviews_submitted: int
    # 自分が作成したPRの再オープン回数の合計（手戻り）
    pull_requests_reopened: int
    # 自分が出したレビューの平均TAT（PR作成→レビュー提出）。対象レビューが無ければNULL
    avg_review_turnaround_hours: float | None


class MemberScore(BaseModel):
    github_login: str
    categories: CategoryScores
    # カテゴリ重みを適用した総合スコア。全メンバーの合計は（全カテゴリに値があれば）1.0
    total: float
    # 上の相対スコアの根拠になる生事実。画面7は点数分解ではなくこちらで根拠を示す
    facts: MemberFacts


class ScoreResponse(BaseModel):
    weights: CategoryWeights
    members: list[MemberScore]
