"use client";

import { CATEGORIES } from "@/constants";
import type { MemberDetail } from "@/types";
import styles from "./ScoreBreakdown.module.css";

type MetricRow = {
  label: string;
  value: string;
  note?: string;
};

// 各カテゴリのスコアと、その根拠となる生データを並べて表示する
export function ScoreBreakdown({ detail }: { detail: MemberDetail }) {
  const { score, weights } = detail;
  const m = score.metrics;

  const rows: Record<string, MetricRow[]> = {
    activity: [
      { label: "Issue作成", value: `${m.issues_opened}件` },
      { label: "PR作成", value: `${m.prs_opened}件` },
      { label: "コメント付きレビュー", value: `${m.reviews_commented}件` },
      {
        label: "Approve / Request changes",
        value: `${m.approvals} / ${m.changes_requested}回`,
      },
      {
        label: "平均レビューTAT",
        value:
          m.avg_review_tat_hours !== null
            ? `${m.avg_review_tat_hours}時間`
            : "—",
      },
    ],
    speed: [
      { label: "獲得SP", value: `${m.sp_earned}pt` },
      { label: "対象作業時間", value: `${m.sp_hours}時間` },
      {
        label: "スループット",
        value: m.sp_throughput !== null ? `${m.sp_throughput} SP/h` : "—",
        note: "SPラベル付きIssueのアサイン〜クローズで計測",
      },
    ],
    quality: [
      { label: "マージ済みPR", value: `${m.prs_merged}件` },
      { label: "バグ起因の手戻り", value: `${m.bugs_assigned}件` },
      { label: "PR再オープン", value: `${m.prs_reopened}回` },
    ],
  };

  return (
    <div className={styles.grid}>
      {CATEGORIES.map((c) => (
        <section key={c.key} className={styles.category}>
          <header
            className={styles.catHeader}
            style={{ borderTopColor: c.color }}
          >
            <span className={styles.catLabel}>{c.label}</span>
            <span className={styles.catScore}>
              <span className="num">{(score.categories[c.key] * 100).toFixed(1)}</span>
              <span className={`num ${styles.catWeight}`}>
                ×{weights[c.key]}%
              </span>
            </span>
          </header>
          <ul className={styles.metrics}>
            {rows[c.key].map((row) => (
              <li key={row.label} className={styles.metric}>
                <span className={styles.metricLabel}>
                  {row.label}
                  {row.note && (
                    <span className={styles.metricNote}>{row.note}</span>
                  )}
                </span>
                <span className={`num ${styles.metricValue}`}>{row.value}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
