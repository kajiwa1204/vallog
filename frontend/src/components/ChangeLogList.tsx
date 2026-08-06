"use client";

import { Badge } from "@/components/ui/Badge";
import type { ChangeKind, ChangeLogEntry } from "@/types";
import styles from "./ChangeLogList.module.css";

const KIND_LABEL: Record<ChangeKind, string> = {
  pull_request: "PR",
  issue: "Issue",
  review: "レビュー",
};

const STATE_TONE: Record<string, "green" | "ochre" | "slate" | "neutral" | "red"> = {
  merged: "green",
  open: "ochre",
  closed: "neutral",
  not_planned: "neutral",
  approved: "green",
  changes_requested: "red",
  commented: "slate",
  dismissed: "neutral",
};

const STATE_LABEL: Record<string, string> = {
  merged: "マージ済み",
  open: "オープン",
  closed: "クローズ",
  // 却下・重複でのクローズ。完了と同じ「クローズ」にすると成果として読まれてしまう
  not_planned: "見送り",
  approved: "承認",
  changes_requested: "要修正",
  commented: "コメント",
  dismissed: "棄却",
};

function formatElapsed(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}分`;
  if (hours < 24) return `${hours.toFixed(1)}時間`;
  return `${(hours / 24).toFixed(1)}日`;
}

// 数字に潰す前の事実だけを並べる（docs/scoring_design.md「Goodhart対策」）。
// 評価や良し悪しは書かず、GitHub上で確認できることだけを出す
function factsOf(entry: ChangeLogEntry): string[] {
  const { story_points, first_review_hours, response_hours, reviewed_by_others, reopened_count } =
    entry.notes;
  const facts: string[] = [];

  if (story_points !== null) facts.push(`SP ${story_points}`);
  if (first_review_hours !== null) facts.push(`初レビューまで ${formatElapsed(first_review_hours)}`);
  if (response_hours !== null) facts.push(`応答 ${formatElapsed(response_hours)}`);
  // 他者レビューが「有る」のは通常なので出さない。無いことのほうが読み手にとっての情報量が多い
  if (reviewed_by_others === false) facts.push("他者レビューなし");
  if (reopened_count) facts.push(`再オープン ${reopened_count}回`);

  return facts;
}

type Props = {
  entries: ChangeLogEntry[];
  emptyText?: string;
  hasMore?: boolean;
  loadingMore?: boolean;
  onLoadMore?: () => void;
};

/**
 * 変化ログの共有プリミティブ（第1層・#77）。
 *
 * props駆動で、取得は呼び出し側（useChangeLog）が担う。ダッシュボード（#13）・
 * メンバー詳細（#14）・分配（#18）が同じ見え方を共有するための土台。
 */
export function ChangeLogList({
  entries,
  emptyText = "まだ変化がありません",
  hasMore = false,
  loadingMore = false,
  onLoadMore,
}: Props) {
  if (entries.length === 0) {
    return <p className={styles.empty}>{emptyText}</p>;
  }

  return (
    <div>
      <ul className={styles.list}>
        {entries.map((entry) => {
          const facts = factsOf(entry);
          return (
            <li key={entry.id}>
              <a
                className={styles.item}
                href={entry.html_url}
                target="_blank"
                rel="noreferrer"
              >
                <div className={styles.head}>
                  <span className={styles.kind}>{KIND_LABEL[entry.kind]}</span>
                  <span className={`num ${styles.number}`}>#{entry.number}</span>
                  <span className={styles.title}>{entry.title}</span>
                  {entry.notes.draft && <Badge tone="neutral">draft</Badge>}
                  <Badge tone={STATE_TONE[entry.state] ?? "neutral"}>
                    {STATE_LABEL[entry.state] ?? entry.state}
                  </Badge>
                </div>
                <div className={styles.meta}>
                  <span className={styles.actor}>{entry.actor_login}</span>
                  <time className={`num ${styles.date}`} dateTime={entry.occurred_at}>
                    {new Date(entry.occurred_at).toLocaleDateString("ja-JP")}
                  </time>
                  {facts.length > 0 && (
                    <span className={styles.facts}>{facts.join(" ・ ")}</span>
                  )}
                </div>
              </a>
            </li>
          );
        })}
      </ul>
      {hasMore && onLoadMore && (
        <button
          type="button"
          className={styles.more}
          onClick={onLoadMore}
          disabled={loadingMore}
        >
          {loadingMore ? "読み込み中..." : "もっと見る"}
        </button>
      )}
    </div>
  );
}
