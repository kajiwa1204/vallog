"use client";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { Attention } from "@/types";
import styles from "./NeedsAttention.module.css";

// ChangeLogList にも同じ整形があるが、あちらは #77 のレビュー中のため取り込まない。
// 集約するなら両PRがマージされてから
function formatElapsed(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}分`;
  if (hours < 24) return `${hours.toFixed(1)}時間`;
  return `${Math.round(hours / 24)}日`;
}

type Row = {
  key: string;
  number: number;
  title: string;
  html_url: string;
  who: string;
  elapsed: number;
  tone: "ochre" | "neutral" | "red";
  toneLabel: string;
};

/**
 * 気にかけること（attention）。止まっているものだけを集める。
 *
 * ここに並ぶのは誰かの評価ではなく、チームが次に手を付ける先。件数が多いことは
 * 個人の落ち度を意味しない（docs/screen_design.md 画面4）。
 *
 * 自分の行に印を付けるのは、全員分が等しく並ぶだけでは「自分がいま動かせるもの」が
 * 読み取れないため。並び順は経過時間の降順のままにする（自分を先頭に寄せると
 * 「一番古いものから手を付ける」という並びの意味が壊れる）。
 */
export function NeedsAttention({
  attention,
  me,
}: {
  attention: Attention;
  me: string | null;
}) {
  const rows: Row[] = [
    ...attention.review_wanted.map((pr) => ({
      key: `review:${pr.number}`,
      number: pr.number,
      title: pr.title,
      html_url: pr.html_url,
      who: pr.author_login,
      elapsed: pr.waiting_hours,
      tone: "ochre" as const,
      toneLabel: "レビュー待ち",
    })),
    ...attention.stalled_issues.map((issue) => ({
      key: `stalled:${issue.number}:${issue.assignee_login}`,
      number: issue.number,
      title: issue.title,
      html_url: issue.html_url,
      who: issue.assignee_login,
      elapsed: issue.stalled_hours,
      tone: "red" as const,
      toneLabel: "担当のまま停滞",
    })),
    ...attention.drafts.map((pr) => ({
      key: `draft:${pr.number}`,
      number: pr.number,
      title: pr.title,
      html_url: pr.html_url,
      who: pr.author_login,
      elapsed: pr.waiting_hours,
      tone: "neutral" as const,
      toneLabel: "draft",
    })),
  ];

  return (
    <Card
      title="気にかけること"
      actions={
        rows.length > 0 && (
          <span className={`num ${styles.count}`}>{rows.length}件</span>
        )
      }
    >
      {rows.length === 0 ? (
        <p className={styles.empty}>止まっているものはありません</p>
      ) : (
        <ul className={styles.list}>
          {rows.map((row) => (
            <li key={row.key}>
              <a
                className={styles.item}
                href={row.html_url}
                target="_blank"
                rel="noreferrer"
              >
                <div className={styles.head}>
                  <Badge tone={row.tone}>{row.toneLabel}</Badge>
                  <span className={`num ${styles.number}`}>#{row.number}</span>
                  <span className={styles.title}>{row.title}</span>
                </div>
                <div className={styles.meta}>
                  <span className={`num ${styles.who}`}>{row.who}</span>
                  {me !== null && row.who === me && (
                    <span className={styles.mine}>あなた</span>
                  )}
                  <span className={`num ${styles.elapsed}`}>
                    {formatElapsed(row.elapsed)}経過
                  </span>
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
