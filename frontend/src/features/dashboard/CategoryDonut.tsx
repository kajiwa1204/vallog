"use client";

import { CATEGORIES } from "@/constants";
import type { CategoryWeights, MemberScore } from "@/types";
import styles from "./CategoryDonut.module.css";

type Props = {
  member: MemberScore;
  weights: CategoryWeights;
};

const R = 54;
const STROKE = 18;
const CIRCUM = 2 * Math.PI * R;

// 選択メンバーの総合スコアに占めるカテゴリ別寄与をドーナツで示す
export function CategoryDonut({ member, weights }: Props) {
  const parts = CATEGORIES.map((c) => ({
    ...c,
    value: (weights[c.key] / 100) * member.categories[c.key],
  }));
  const total = parts.reduce((sum, p) => sum + p.value, 0);

  let offset = 0;
  const segments = parts.map((p) => {
    const frac = total > 0 ? p.value / total : 0;
    const seg = { ...p, frac, dashOffset: -offset * CIRCUM };
    offset += frac;
    return seg;
  });

  return (
    <div className={styles.wrap}>
      <div className={styles.donut}>
        <svg viewBox="0 0 140 140" role="img" aria-label="カテゴリ別スコア内訳">
          <circle
            cx="70"
            cy="70"
            r={R}
            fill="none"
            stroke="var(--surface-dim)"
            strokeWidth={STROKE}
          />
          {total > 0 &&
            segments.map((s) => (
              <circle
                key={s.key}
                cx="70"
                cy="70"
                r={R}
                fill="none"
                stroke={s.color}
                strokeWidth={STROKE}
                strokeDasharray={`${Math.max(s.frac * CIRCUM - 1.5, 0)} ${CIRCUM}`}
                strokeDashoffset={s.dashOffset}
                transform="rotate(-90 70 70)"
              />
            ))}
        </svg>
        <div className={styles.center}>
          <span className={`num ${styles.score}`}>
            {(member.total * 100).toFixed(1)}
          </span>
          <span className={styles.scoreLabel}>総合スコア</span>
        </div>
      </div>

      <ul className={styles.breakdown}>
        {segments.map((s) => (
          <li key={s.key} className={styles.item}>
            <span className={styles.swatch} style={{ background: s.color }} />
            <span className={styles.label}>{s.label}</span>
            <span className={`num ${styles.value}`}>
              {(member.categories[s.key] * 100).toFixed(1)}
            </span>
            <span className={`num ${styles.weight}`}>×{weights[s.key]}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
