"use client";

import { Badge } from "@/components/ui/Badge";
import { formatElapsed } from "@/lib/duration";
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

/** 日付の見出し。今日・昨日だけ相対にする（それ以上は相対にすると数える手間が増える） */
function formatDayHeading(iso: string, today: Date): string {
  const d = new Date(iso);
  const days = Math.round(
    (new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() -
      new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()) /
      86400000,
  );
  if (days === 0) return "今日";
  if (days === 1) return "昨日";
  return d.toLocaleDateString("ja-JP", {
    month: "numeric",
    day: "numeric",
    weekday: "short",
  });
}

function dayKeyOf(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

type DayGroup = {
  key: string;
  heading: string;
  entries: ChangeLogEntry[];
};

/** 同じ日のエントリを束ねる。entries は新しい順に並んでいる前提 */
function groupByDay(entries: ChangeLogEntry[], today: Date): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const entry of entries) {
    const key = dayKeyOf(entry.occurred_at);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.entries.push(entry);
    else
      groups.push({
        key,
        heading: formatDayHeading(entry.occurred_at, today),
        entries: [entry],
      });
  }
  return groups;
}

type Props = {
  entries: ChangeLogEntry[];
  emptyText?: string;
  hasMore?: boolean;
  loadingMore?: boolean;
  onLoadMore?: () => void;
  // これより後に起きた変化に新着の印を付ける。null なら印を出さない
  newSince?: string | null;
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
  newSince = null,
}: Props) {
  if (entries.length === 0) {
    return <p className={styles.empty}>{emptyText}</p>;
  }

  // 日付でまとめるのは、フラットに並ぶと「今日何があったか」が読み取れないため。
  // 日付は各行にも出ていたが、行の属性であって構造ではなかった
  const groups = groupByDay(entries, new Date());
  const newCount = newSince
    ? entries.filter((e) => e.occurred_at > newSince).length
    : 0;

  return (
    <div>
      {groups.map((group) => (
        <section key={group.key} className={styles.day}>
          {/* Card のタイトルが h2 なので、その直下の区切りは h3。
              気にかけること・動いている領域の群見出しと規則を揃える */}
          <h3 className={styles.dayHeading}>
            {group.heading}
            <span className={`num ${styles.dayCount}`}>
              {group.entries.length}
            </span>
          </h3>
          <ul className={styles.list}>
            {group.entries.map((entry) => {
              const facts = factsOf(entry);
              const isNew = newSince !== null && entry.occurred_at > newSince;
              return (
                <li key={entry.id}>
                  <a
                    className={styles.item}
                    href={entry.html_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <div className={styles.head}>
                      {/* ロールを持たない空の span に aria-label を付けても
                          アクセシブルネームにならず読まれない。視覚的に隠した
                          テキストにして、親リンクの読み上げに自然に混ぜる */}
                      {isNew && (
                        <>
                          <span className={styles.new} aria-hidden="true" />
                          <span className="visually-hidden">
                            前回見たとき以降の変化
                          </span>
                        </>
                      )}
                      <span className={styles.kind}>
                        {KIND_LABEL[entry.kind]}
                      </span>
                      <span className={`num ${styles.number}`}>
                        #{entry.number}
                      </span>
                      <span className={styles.title}>{entry.title}</span>
                      {entry.notes.draft && <Badge tone="neutral">draft</Badge>}
                      <Badge tone={STATE_TONE[entry.state] ?? "neutral"}>
                        {STATE_LABEL[entry.state] ?? entry.state}
                      </Badge>
                    </div>
                    <div className={styles.meta}>
                      <span className={styles.actor}>{entry.actor_login}</span>
                      {facts.length > 0 && (
                        <span className={styles.facts}>
                          {facts.join(" ・ ")}
                        </span>
                      )}
                    </div>
                  </a>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {newCount > 0 && (
        <p className={styles.newSummary}>
          前回見たとき以降の変化に印を付けています（{newCount}件）
        </p>
      )}
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
