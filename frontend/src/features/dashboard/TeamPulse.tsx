"use client";

import { Card } from "@/components/ui/Card";
import type { PulseDay } from "@/types";
import styles from "./TeamPulse.module.css";

const KINDS = [
  { key: "pull_requests", label: "PR", color: "var(--green)" },
  { key: "issues", label: "Issue", color: "var(--ochre)" },
  { key: "reviews", label: "レビュー", color: "var(--slate)" },
] as const;

function totalOf(day: PulseDay): number {
  return day.pull_requests + day.issues + day.reviews;
}

function formatDay(iso: string): string {
  // バックエンドが閲覧者のオフセットで畳んだ日付。ここで Date に通すと再びUTC解釈で
  // ずれるため、文字列のまま切り出す
  const [, month, day] = iso.split("-");
  return `${Number(month)}/${Number(day)}`;
}

/**
 * 活動リズム（pulse）。直近N日の日次バケット。
 *
 * 変化ログを日付で畳んだものなので、バーの高い日は必ず下の一覧に対応する行がある。
 */
export function TeamPulse({ days }: { days: PulseDay[] }) {
  const max = Math.max(...days.map(totalOf), 1);
  const total = days.reduce((sum, d) => sum + totalOf(d), 0);

  return (
    <Card
      title="活動リズム"
      actions={
        <span className={styles.range}>
          {days.length > 0 &&
            `${formatDay(days[0].date)} 〜 ${formatDay(days[days.length - 1].date)}`}
        </span>
      }
    >
      {total === 0 ? (
        <p className={styles.empty}>この期間の動きはまだありません</p>
      ) : (
        <>
          <div
            className={styles.chart}
            role="img"
            aria-label={`直近${days.length}日で${total}件の変化`}
          >
            {days.map((day) => {
              const dayTotal = totalOf(day);
              return (
                <div key={day.date} className={styles.column}>
                  <div className={styles.track}>
                    <div
                      className={styles.bar}
                      style={{ height: `${(dayTotal / max) * 100}%` }}
                      title={`${formatDay(day.date)} — PR ${day.pull_requests} / Issue ${day.issues} / レビュー ${day.reviews}`}
                    >
                      {KINDS.map((kind) => (
                        <span
                          key={kind.key}
                          className={styles.segment}
                          style={{
                            flexGrow: day[kind.key],
                            background: kind.color,
                          }}
                        />
                      ))}
                    </div>
                  </div>
                  <span className={`num ${styles.tick}`}>
                    {formatDay(day.date)}
                  </span>
                </div>
              );
            })}
          </div>

          <div className={styles.legend}>
            {KINDS.map((kind) => (
              <span key={kind.key} className={styles.legendItem}>
                <span
                  className={styles.swatch}
                  style={{ background: kind.color }}
                />
                {kind.label}
              </span>
            ))}
            <span className={`num ${styles.total}`}>合計 {total}</span>
          </div>
        </>
      )}
    </Card>
  );
}
