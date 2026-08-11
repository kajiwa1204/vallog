"use client";

import { Card } from "@/components/ui/Card";
import { type ActivityWeek, weekTotal } from "./activity";
import styles from "./ActivityChart.module.css";

const KINDS = [
  { key: "pullRequests", label: "PR", color: "var(--green)" },
  { key: "issues", label: "Issue", color: "var(--ochre)" },
  { key: "reviews", label: "レビュー", color: "var(--slate)" },
] as const;

function formatWeek(weekStart: string): string {
  // ローカル日付として組み立てられた文字列。Date に通すとUTC解釈で1日ずれる
  const [, month, day] = weekStart.split("-");
  return `${Number(month)}/${Number(day)}`;
}

type Props = {
  weeks: ActivityWeek[];
  truncated: boolean;
};

/**
 * 活動量の推移（#14）。週の始まり（月曜）ごとの件数。
 *
 * ダッシュボードの活動リズム（TeamPulse）が日次なのに対して週次にしているのは、
 * 個人の活動がチームより疎で、日次だと大半が空バーになりリズムが読めないため。
 * 同じ見え方を共有するが、片方はサーバが畳んだ日次バケット、こちらはクライアントが
 * 変化ログから畳んだ週次バケットで出所が違うので、コンポーネントは分けてある。
 *
 * 高さは件数そのもの。他のメンバーと並べず、順位も出さない
 * （docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
 */
export function ActivityChart({ weeks, truncated }: Props) {
  const max = Math.max(...weeks.map(weekTotal), 1);
  const total = weeks.reduce((sum, week) => sum + weekTotal(week), 0);

  return (
    <Card
      title="活動量の推移"
      actions={
        weeks.length > 0 && (
          <span className={`num ${styles.range}`}>
            {formatWeek(weeks[0].weekStart)} 〜{" "}
            {formatWeek(weeks[weeks.length - 1].weekStart)} の週ごと
          </span>
        )
      }
    >
      {weeks.length === 0 ? (
        <p className={styles.empty}>まだ記録がありません</p>
      ) : (
        <>
          <div
            className={styles.chart}
            role="img"
            aria-label={`直近${weeks.length}週で${total}件の記録`}
          >
            {weeks.map((week) => {
              const weekly = weekTotal(week);
              return (
                <div key={week.weekStart} className={styles.column}>
                  <div className={styles.track}>
                    <div
                      className={styles.bar}
                      style={{ height: `${(weekly / max) * 100}%` }}
                      title={`${formatWeek(week.weekStart)} の週 — PR ${week.pullRequests} / Issue ${week.issues} / レビュー ${week.reviews}`}
                    >
                      {KINDS.map((kind) => (
                        <span
                          key={kind.key}
                          className={styles.segment}
                          style={{ flexGrow: week[kind.key], background: kind.color }}
                        />
                      ))}
                    </div>
                  </div>
                  <span className={`num ${styles.tick}`}>
                    {formatWeek(week.weekStart)}
                  </span>
                </div>
              );
            })}
          </div>

          <div className={styles.legend}>
            {KINDS.map((kind) => (
              <span key={kind.key} className={styles.legendItem}>
                <span className={styles.swatch} style={{ background: kind.color }} />
                {kind.label}
              </span>
            ))}
          </div>

          {truncated && (
            <p className={styles.note}>
              読み込み済みの記録の範囲で描いています。これより古い週は含まれていません。
            </p>
          )}
        </>
      )}
    </Card>
  );
}
