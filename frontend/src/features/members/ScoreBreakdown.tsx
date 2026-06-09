import styles from "./ScoreBreakdown.module.css";
import type { MemberScore } from "@/types";

type Props = { score: MemberScore };

const rows: Array<{
  key: keyof MemberScore["breakdown"];
  label: string;
  desc: string;
  color: string;
}> = [
  { key: "issue", label: "Issue", desc: "解決済みIssueの起票・対応", color: "var(--chart-1)" },
  { key: "pr", label: "PR", desc: "マージされたPRの規模・件数", color: "var(--chart-2)" },
  { key: "review", label: "Review", desc: "他メンバーのPRへのレビュー", color: "var(--chart-3)" },
  { key: "tat", label: "TAT", desc: "リードタイム・反応速度", color: "var(--chart-4)" },
  { key: "sp", label: "SP", desc: "ストーリーポイントラベル", color: "var(--chart-5)" },
];

export function ScoreBreakdown({ score }: Props) {
  const max = Math.max(...rows.map((r) => score.breakdown[r.key]));
  return (
    <div className={styles.wrapper}>
      {rows.map((r) => (
        <div key={r.key} className={styles.row}>
          <div className={styles.head}>
            <div className={styles.labelGroup}>
              <span className={styles.label}>{r.label}</span>
              <span className={styles.desc}>{r.desc}</span>
            </div>
            <div className={styles.value}>{score.breakdown[r.key]}</div>
          </div>
          <div className={styles.barOuter}>
            <div
              className={styles.barFill}
              style={{
                width: `${(score.breakdown[r.key] / max) * 100}%`,
                backgroundColor: r.color,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
