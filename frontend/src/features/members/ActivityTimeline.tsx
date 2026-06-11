"use client";

import type { TimelinePoint } from "@/types";
import styles from "./ActivityTimeline.module.css";

const SERIES = [
  { key: "prs", label: "PR", color: "var(--green)" },
  { key: "issues", label: "Issue", color: "var(--ochre)" },
  { key: "reviews", label: "レビュー", color: "var(--slate)" },
] as const;

// 直近12週の活動量を週次の積み上げ棒で表示する
export function ActivityTimeline({ timeline }: { timeline: TimelinePoint[] }) {
  const max = Math.max(
    ...timeline.map((p) => p.prs + p.issues + p.reviews),
    1,
  );

  return (
    <div>
      <div className={styles.chart}>
        {timeline.map((p) => {
          const total = p.prs + p.issues + p.reviews;
          const date = new Date(p.week_start);
          return (
            <div
              key={p.week_start}
              className={styles.col}
              title={`${date.toLocaleDateString("ja-JP")}週: PR ${p.prs} / Issue ${p.issues} / レビュー ${p.reviews}`}
            >
              <div className={styles.barArea}>
                {total > 0 && (
                  <div
                    className={styles.bar}
                    style={{ height: `${(total / max) * 100}%` }}
                  >
                    {SERIES.map(
                      (s) =>
                        p[s.key] > 0 && (
                          <span
                            key={s.key}
                            className={styles.segment}
                            style={{
                              flexGrow: p[s.key],
                              background: s.color,
                            }}
                          />
                        ),
                    )}
                  </div>
                )}
              </div>
              <span className={`num ${styles.tick}`}>
                {date.getMonth() + 1}/{date.getDate()}
              </span>
            </div>
          );
        })}
      </div>
      <div className={styles.legend}>
        {SERIES.map((s) => (
          <span key={s.key} className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
