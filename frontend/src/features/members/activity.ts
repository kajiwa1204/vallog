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

/**
 * 内訳の1項目。**同じ種別の内訳は必ず互いに排他で、合計は total に一致する。**
 *
 * 独立した filter を並べる書き方をやめたのは、それが合計と合わない内訳を静かに作る
 * ためだった。draft PR は GitHub 上で state="open" なので「オープン」と「draft」に
 * 二重計上され、逆にマージされずに閉じたPRとレビューの dismissed はどの内訳にも
 * 入らずに消えていた。打ち消し合って和がたまたま合う場合すらある。
 *
 * 各エントリをちょうど1つのバケットに落とす分割にすれば、「和＝合計」が構成上の
 * 帰結になり、状態が1つ増えても静かに壊れない（未知の状態は「その他」に落ちる）。
 */
export type Breakdown = {
  label: string;
  count: number;
};

export type ContributionFacts = {
  // PR（本人が作成者の行）
  prsOpened: number;
  /** 合計 prsOpened の排他な内訳。0 の項目は含まない */
  prBreakdown: Breakdown[];
  // 他者レビューが1件も付いていないPR。「見られていない自分のPR」に気づくための事実。
  // draft は「まだ頼んでいない」ので含めない（作業中のものを見られていないと言わない）
  prsWithoutReview: number;
  // Issue（起票または担当）。変化ログはこの2つを区別しないので、まとめて数える
  issues: number;
  issueBreakdown: Breakdown[];
  // 完了IssueのSPラベルの合計。SPラベルの付いた完了Issueが1つも無ければ null
  // （「SP 0」と「SPを運用していない」を区別する）
  storyPointsCompleted: number | null;
  // レビュー（本人が出した行）
  reviews: number;
  reviewBreakdown: Breakdown[];
  // 自分がそのPRに最初に応答するまでの時間。同じPRへの2件目以降は議論の往復であって
  // 「返すまでの時間」ではないので、PRごとに最初の1件だけを採る。畳まずに全レビュー行を
  // 数えると、丁寧に往復した人ほど悪い数字が出る（バックエンドは同一PRへの複数レビューを
  // 畳まない。services/changelog.py の build_changelog を参照）。
  // 中央値なのは、1件の放置が平均を支配して「普段どのくらいで返しているか」が
  // 読めなくなるため
  medianResponseHours: number | null;
  // 自分のPRに最初の他者レビューが付くまでの時間。上と同じ区間を逆側から見た値で、
  // こちらは自分ではなくチームの応答（PR行は1PRにつき1行なので畳む必要がない）
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

/**
 * 分類の結果を、宣言した順のラベルで数え上げる。
 *
 * classify はどのエントリに対しても必ず1つのラベルを返すこと（返り値の型で強制する）。
 * これにより sum(内訳) === entries.length が構成上保証される。
 */
function breakdownOf<L extends string>(
  entries: ChangeLogEntry[],
  order: readonly L[],
  classify: (entry: ChangeLogEntry) => L,
  labels: Record<L, string>,
): Breakdown[] {
  const counts = new Map<L, number>(order.map((key) => [key, 0]));
  for (const entry of entries) {
    const key = classify(entry);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  // 0 の項目は並べない（0が並ぶと読む項目が埋もれる）。落としても和は変わらない
  return order
    .filter((key) => (counts.get(key) ?? 0) > 0)
    .map((key) => ({ label: labels[key], count: counts.get(key) ?? 0 }));
}

const PR_STATES = ["merged", "closed", "draft", "open", "other"] as const;
const ISSUE_STATES = ["completed", "not_planned", "open", "other"] as const;
const REVIEW_STATES = [
  "approved",
  "changes_requested",
  "commented",
  "dismissed",
  "other",
] as const;

/**
 * PRの状態を1つに決める。
 *
 * draft より先にマージ・クローズを見るのは、draft が「まだ動いている」ことの印で、
 * 決着が付いた後は決着のほうが読み手の知りたい事実になるため。
 * draft を state より先に見ないのは、GitHubが draft にも state="open" を返すため
 * （先に open で拾うと draft が消える）。
 */
function prState(entry: ChangeLogEntry): (typeof PR_STATES)[number] {
  if (entry.state === "merged") return "merged";
  if (entry.state === "closed") return "closed";
  if (entry.notes.draft === true) return "draft";
  if (entry.state === "open") return "open";
  return "other";
}

export function summarizeContribution(entries: ChangeLogEntry[]): ContributionFacts {
  const prs = entries.filter((e) => e.kind === "pull_request");
  const issues = entries.filter((e) => e.kind === "issue");
  const reviews = entries.filter((e) => e.kind === "review");

  const sp = issues
    .filter((e) => e.state === "closed")
    .map((e) => e.notes.story_points)
    .filter((v): v is number => v !== null);

  // PRごとに最初の応答だけを残す。同じPRへの2件目以降は議論の往復で、
  // 「返すまでの時間」ではない
  const firstResponseByPr = new Map<number, number>();
  for (const review of reviews) {
    const hours = review.notes.response_hours;
    if (hours === null) continue;
    const current = firstResponseByPr.get(review.number);
    if (current === undefined || hours < current)
      firstResponseByPr.set(review.number, hours);
  }

  const firstReviewHours = prs
    .map((e) => e.notes.first_review_hours)
    .filter((v): v is number => v !== null);

  return {
    prsOpened: prs.length,
    prBreakdown: breakdownOf(prs, PR_STATES, prState, {
      merged: "マージ済み",
      closed: "クローズ",
      draft: "draft",
      open: "オープン",
      other: "その他",
    }),
    prsWithoutReview: prs.filter(
      (e) => e.notes.reviewed_by_others === false && e.notes.draft !== true,
    ).length,
    issues: issues.length,
    issueBreakdown: breakdownOf(
      issues,
      ISSUE_STATES,
      (e) =>
        e.state === "closed"
          ? "completed"
          : e.state === "not_planned"
            ? "not_planned"
            : e.state === "open"
              ? "open"
              : "other",
      {
        completed: "完了",
        not_planned: "見送り",
        open: "進行中",
        other: "その他",
      },
    ),
    storyPointsCompleted: sp.length > 0 ? sp.reduce((a, b) => a + b, 0) : null,
    reviews: reviews.length,
    reviewBreakdown: breakdownOf(
      reviews,
      REVIEW_STATES,
      (e) =>
        REVIEW_STATES.includes(e.state as (typeof REVIEW_STATES)[number])
          ? (e.state as (typeof REVIEW_STATES)[number])
          : "other",
      {
        approved: "承認",
        changes_requested: "要修正",
        commented: "コメント",
        dismissed: "棄却",
        other: "その他",
      },
    ),
    medianResponseHours: median([...firstResponseByPr.values()]),
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
 *
 * 記録がすべて窓より古いときは空配列を返す。0のバーを12本並べて「直近12週で0件」と
 * 言うと、その真横で「125件を数えた」と言っているカードと矛盾した印象になる。
 * 呼び出し側は空配列を「この窓に記録が無い」として、最新の記録がいつかを添えて出す。
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
  const shown =
    truncated && startsAtDataEdge && weeks.length > 1 ? weeks.slice(1) : weeks;

  // 記録はあるが、すべてこの窓より古い（長く休止している人・離脱した人のページ）
  return shown.some((week) => weekTotal(week) > 0) ? shown : [];
}

export function weekTotal(week: ActivityWeek): number {
  return week.pullRequests + week.issues + week.reviews;
}
