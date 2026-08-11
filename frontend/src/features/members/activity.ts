/**
 * メンバー詳細（画面5）の集計。変化ログのエントリだけを入力に取る純粋関数。
 *
 * サーバに集計APIを足さず、**画面に並んでいる行そのもの**から数えているのが要点。
 * この画面の用途は「自分の貢献が正しく記録されているか」の検算なので、数字は下の
 * 一覧を数えれば必ず再現できなければならない。サーバがキャッシュ全件から別途集計
 * すると、表示中の行を数えても合わない数字が出て、検算という目的そのものが壊れる。
 *
 * 代償は limit による打ち切りで、これは呼び出し側が truncated を渡して明示する。
 *
 * スコアは出さない（docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
 * ここに並ぶのは重み付けも順位付けもしない生の件数と時間だけ。
 *
 * React に依存しないのは、テスト基盤（#66）が立った直後にそのままテストできる形に
 * しておくため。
 */

import type { ChangeLogEntry } from "@/types";

export type ContributionFacts = {
  // PR（本人が作成者の行）
  prsOpened: number;
  prsMerged: number;
  prsOpen: number;
  prsDraft: number;
  // 他者レビューが1件も付いていないPR。「見られていない自分のPR」に気づくための事実
  prsWithoutReview: number;
  // Issue（起票または担当）。変化ログはこの2つを区別しないので、まとめて数える
  issues: number;
  issuesCompleted: number;
  issuesNotPlanned: number;
  // 完了IssueのSPラベルの合計。SPラベルの付いた完了Issueが1つも無ければ null
  // （「SP 0」と「SPを運用していない」を区別する）
  storyPointsCompleted: number | null;
  // レビュー（本人が出した行）
  reviews: number;
  approvals: number;
  changesRequested: number;
  reviewComments: number;
  // 自分がレビューを返すまでの時間。中央値なのは、1件の放置が平均を支配して
  // 「普段どのくらいで返しているか」が読めなくなるため
  medianResponseHours: number | null;
  // 自分のPRに最初の他者レビューが付くまでの時間。上と同じ区間を逆側から見た値で、
  // こちらは自分ではなくチームの応答
  medianFirstReviewHours: number | null;
};

export type ActivityWeek = {
  /** 週の開始日（月曜）のローカル日付 YYYY-MM-DD */
  weekStart: string;
  pullRequests: number;
  issues: number;
  reviews: number;
};

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[mid];
  return Math.round(((sorted[mid - 1] + sorted[mid]) / 2) * 10) / 10;
}

export function summarizeContribution(entries: ChangeLogEntry[]): ContributionFacts {
  const prs = entries.filter((e) => e.kind === "pull_request");
  const issues = entries.filter((e) => e.kind === "issue");
  const reviews = entries.filter((e) => e.kind === "review");

  const completed = issues.filter((e) => e.state === "closed");
  const sp = completed
    .map((e) => e.notes.story_points)
    .filter((v): v is number => v !== null);

  const responseHours = reviews
    .map((e) => e.notes.response_hours)
    .filter((v): v is number => v !== null);
  const firstReviewHours = prs
    .map((e) => e.notes.first_review_hours)
    .filter((v): v is number => v !== null);

  return {
    prsOpened: prs.length,
    prsMerged: prs.filter((e) => e.state === "merged").length,
    prsOpen: prs.filter((e) => e.state === "open").length,
    prsDraft: prs.filter((e) => e.notes.draft === true).length,
    prsWithoutReview: prs.filter((e) => e.notes.reviewed_by_others === false).length,
    issues: issues.length,
    issuesCompleted: completed.length,
    issuesNotPlanned: issues.filter((e) => e.state === "not_planned").length,
    storyPointsCompleted: sp.length > 0 ? sp.reduce((a, b) => a + b, 0) : null,
    reviews: reviews.length,
    approvals: reviews.filter((e) => e.state === "approved").length,
    changesRequested: reviews.filter((e) => e.state === "changes_requested").length,
    reviewComments: reviews.filter((e) => e.state === "commented").length,
    medianResponseHours: median(responseHours),
    medianFirstReviewHours: median(firstReviewHours),
  };
}

/** ローカル日付の YYYY-MM-DD。toISOString はUTCに寄せてしまうので使わない */
function localDateKey(d: Date): string {
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

/** その日を含む週の月曜 00:00（ローカル） */
function startOfWeek(d: Date): Date {
  const start = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  // getDay() は日曜が0。月曜起点にするため日曜だけ6日戻す
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  return start;
}

function addWeeks(d: Date, weeks: number): Date {
  const next = new Date(d);
  // ミリ秒を足すのではなく日付を進める。夏時間のある地域では 7*86400000 が1時間ずれ、
  // 週の開始が前日に転がる
  next.setDate(next.getDate() + weeks * 7);
  return next;
}

/**
 * 活動量を週次バケットに畳む（古い→新しい）。
 *
 * ダッシュボード（画面4）の活動リズムが日次なのに対してこちらを週次にするのは、
 * 個人の活動がチームより疎で、日次だと大半が空バーになりリズムが読めないため。
 *
 * 打ち切り（truncated）があるときは最も古い週を落とす。変化ログは新しい順に limit で
 * 切られるので、いちばん古い週だけは「その週の一部」しか手元に無い。落とさずに描くと、
 * 実際は動いていた週が低いバーとして出て事実に反する。
 */
export function buildActivityWeeks(
  entries: ChangeLogEntry[],
  now: Date,
  { maxWeeks = 12, truncated = false }: { maxWeeks?: number; truncated?: boolean } = {},
): ActivityWeek[] {
  if (entries.length === 0) return [];

  const current = startOfWeek(now);
  const buckets = new Map<string, ActivityWeek>();
  let oldest = current;

  for (const entry of entries) {
    const weekStart = startOfWeek(new Date(entry.occurred_at));
    const key = localDateKey(weekStart);
    if (weekStart < oldest) oldest = weekStart;

    const bucket = buckets.get(key) ?? {
      weekStart: key,
      pullRequests: 0,
      issues: 0,
      reviews: 0,
    };
    if (entry.kind === "pull_request") bucket.pullRequests += 1;
    else if (entry.kind === "issue") bucket.issues += 1;
    else bucket.reviews += 1;
    buckets.set(key, bucket);
  }

  // データより手前の空週を並べても読み手に何も伝わらないので、実データの開始週で切る
  const limitWeek = addWeeks(current, -(maxWeeks - 1));
  const from = oldest > limitWeek ? oldest : limitWeek;

  const weeks: ActivityWeek[] = [];
  for (let cursor = from; cursor <= current; cursor = addWeeks(cursor, 1)) {
    const key = localDateKey(cursor);
    weeks.push(
      buckets.get(key) ?? { weekStart: key, pullRequests: 0, issues: 0, reviews: 0 },
    );
  }

  // 落とすのは、範囲の先頭が「データの端」でもあるときだけ。maxWeeks で切った先頭は
  // それより古い記録も手元にあるので、その週は欠けていない。
  // 1週しか無いときは落とさない（何も残らないため。打ち切りは注記で伝える）
  const startsAtDataEdge = from.getTime() === oldest.getTime();
  return truncated && startsAtDataEdge && weeks.length > 1 ? weeks.slice(1) : weeks;
}

export function weekTotal(week: ActivityWeek): number {
  return week.pullRequests + week.issues + week.reviews;
}
