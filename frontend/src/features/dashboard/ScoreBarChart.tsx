"use client";

import { CATEGORIES } from "@/constants";
import { Avatar } from "@/components/ui/Avatar";
import type { CategoryWeights, MemberScore } from "@/types";
import styles from "./ScoreBarChart.module.css";

type Props = {
  members: MemberScore[];
  weights: CategoryWeights;
  selected: string | null;
  onSelect: (login: string) => void;
};

// シグネチャ要素: カテゴリ3色の積層バー。総合スコアの構成が一目で読める
export function ScoreBarChart({ members, weights, selected, onSelect }: Props) {
  const max = Math.max(...members.map((m) => m.total), 0.0001);

  return (
    <div className={styles.chart}>
      {members.map((m) => {
        const widthPct = (m.total / max) * 100;
        return (
          <button
            key={m.github_login}
            className={`${styles.row} ${
              selected === m.github_login ? styles.selected : ""
            }`}
            onClick={() => onSelect(m.github_login)}
          >
            <span className={styles.member}>
              <Avatar login={m.github_login} url={m.avatar_url} size={24} />
              <span className={`num ${styles.login}`}>{m.github_login}</span>
            </span>
            <span className={styles.track}>
              <span className={styles.bar} style={{ width: `${widthPct}%` }}>
                {CATEGORIES.map((c) => {
                  const part =
                    m.total > 0
                      ? ((weights[c.key] / 100) * m.categories[c.key]) / m.total
                      : 0;
                  return (
                    <span
                      key={c.key}
                      className={styles.segment}
                      style={{
                        flexGrow: part,
                        background: c.color,
                      }}
                    />
                  );
                })}
              </span>
            </span>
            <span className={`num ${styles.total}`}>
              {(m.total * 100).toFixed(1)}
            </span>
          </button>
        );
      })}

      <div className={styles.legend}>
        {CATEGORIES.map((c) => (
          <span key={c.key} className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: c.color }} />
            {c.label}
          </span>
        ))}
      </div>
    </div>
  );
}
