// features横断の共通型定義（バックエンドschemasと対応）

export type User = {
  id: string;
  github_login: string;
  avatar_url: string | null;
};

export type TokenResponse = {
  access_token: string;
  user: User;
};

export type CategoryWeights = {
  activity: number;
  speed: number;
  quality: number;
};

export type CategoryKey = keyof CategoryWeights;

export type ProjectListItem = {
  id: string;
  name: string;
  repo_owner: string;
  repo_name: string;
  member_count: number;
};

export type Project = {
  id: string;
  name: string;
  repo_owner: string;
  repo_name: string;
  weights: CategoryWeights;
  member_count: number;
  github_synced_at: string | null;
  created_at: string;
};

export type RepoOption = {
  owner: string;
  name: string;
  full_name: string;
  private: boolean;
  description: string | null;
};

export type Member = {
  github_login: string;
  avatar_url: string | null;
  is_member: boolean;
};

export type Invitation = {
  token: string;
  url: string;
  expires_at: string;
};

export type InvitationInfo = {
  project_id: string;
  project_name: string;
  repo_owner: string;
  repo_name: string;
  member_count: number;
  expires_at: string;
};

export type JoinResponse = {
  project_id: string;
};

export type MetricRaw = {
  issues_opened: number;
  prs_opened: number;
  prs_merged: number;
  reviews_commented: number;
  approvals: number;
  changes_requested: number;
  avg_review_tat_hours: number | null;
  sp_earned: number;
  sp_hours: number;
  sp_throughput: number | null;
  bugs_assigned: number;
  prs_reopened: number;
};

export type CategoryScores = {
  activity: number;
  speed: number;
  quality: number;
};

export type MemberScore = {
  github_login: string;
  avatar_url: string | null;
  is_registered: boolean;
  total: number;
  categories: CategoryScores;
  metrics: MetricRaw;
};

export type ScoreResponse = {
  synced_at: string | null;
  weights: CategoryWeights;
  members: MemberScore[];
};

export type TimelinePoint = {
  week_start: string;
  prs: number;
  issues: number;
  reviews: number;
};

export type GitHubItem = {
  number: number;
  title: string;
  state: string;
  html_url: string;
  created_at: string;
  extra: string | null;
};

export type Summary = {
  github_login: string;
  content: string;
  generated_at: string;
};

export type MemberDetail = {
  score: MemberScore;
  weights: CategoryWeights;
  synced_at: string | null;
  timeline: TimelinePoint[];
  recent_prs: GitHubItem[];
  recent_issues: GitHubItem[];
  recent_reviews: GitHubItem[];
  summary: Summary | null;
};

export type DistributionItem = {
  github_login: string;
  avatar_url: string | null;
  ratio: string;
  amount: string | null;
};

export type Proposal = {
  id: string;
  title: string;
  status: "draft" | "agreed";
  total_amount: string | null;
  weights: CategoryWeights;
  items: DistributionItem[];
  creator_login: string;
  created_at: string;
  agreed_at: string | null;
};

export type ProposalListItem = {
  id: string;
  title: string;
  status: "draft" | "agreed";
  total_amount: string | null;
  creator_login: string;
  created_at: string;
  agreed_at: string | null;
};

export type EditLog = {
  id: string;
  editor_login: string;
  editor_avatar_url: string | null;
  reason: string;
  before_items: { items: { github_login: string; ratio: string }[] };
  after_items: { items: { github_login: string; ratio: string }[] };
  created_at: string;
};

export type SummaryJob = {
  id: string;
  github_login: string;
  status: "pending" | "running" | "succeeded" | "failed";
  total_prs: number;
  done_prs: number;
  pr_number: number | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

export type PRSummaryItem = {
  pr_number: number;
  title: string;
  html_url: string;
  state: "merged" | "draft" | "open" | "closed";
  content: string | null;
  generated_at: string | null;
  job: SummaryJob | null;
};

// 変化ログ（第1層・AIなし）。backend/app/schemas/changelog.py と対応する
export type ChangeKind = "pull_request" | "issue" | "review";

// 各フィールドが null 許容なのは「非適用」と「意味のあるゼロ」を区別するため。
// Issue行の reopened_count は 0 ではなく null（再オープンの概念を適用しない）で来る
export type ChangeLogNotes = {
  story_points: number | null;
  // PR行のみ: 作成から最初の他者レビューまで（PR作者の待ち時間）
  first_review_hours: number | null;
  // レビュー行のみ: PR作成から自分が出すまで（レビュアーの応答時間）
  response_hours: number | null;
  reviewed_by_others: boolean | null;
  reopened_count: number | null;
  draft: boolean | null;
};

export type ChangeLogEntry = {
  // number は kind をまたいで衝突するため、一覧のキーには id を使う
  id: string;
  kind: ChangeKind;
  number: number;
  title: string;
  actor_login: string;
  // PR: merged/open/closed、Issue: open/closed/not_planned、
  // レビュー: approved/changes_requested/commented/dismissed
  state: string;
  occurred_at: string;
  html_url: string;
  notes: ChangeLogNotes;
};

export type ChangeLogResponse = {
  entries: ChangeLogEntry[];
  has_more: boolean;
};

// チーム状況パネル4種（画面4）。backend/app/schemas/dashboard.py と対応する。
// スコアは含まない（docs/scoring_design.md「Goodhart対策とスコアの事後開示」）
export type PulseDay = {
  // YYYY-MM-DD。バックエンドが tz_offset_minutes を見て畳んだローカル日付
  date: string;
  pull_requests: number;
  issues: number;
  reviews: number;
};

export type AttentionPullRequest = {
  number: number;
  title: string;
  author_login: string;
  html_url: string;
  opened_at: string;
  // 作成から現在まで（＝まだ止まっている時間）
  waiting_hours: number;
  draft: boolean;
};

export type AttentionIssue = {
  number: number;
  title: string;
  html_url: string;
  assignee_login: string;
  assigned_at: string;
  stalled_hours: number;
};

export type Attention = {
  review_wanted: AttentionPullRequest[];
  drafts: AttentionPullRequest[];
  stalled_issues: AttentionIssue[];
};

export type Theme = {
  label: string;
  open_count: number;
  closed_count: number;
};

export type DashboardResponse = {
  // null なら初回同期がまだ完了していない
  synced_at: string | null;
  pulse: PulseDay[];
  attention: Attention;
  themes: Theme[];
};
