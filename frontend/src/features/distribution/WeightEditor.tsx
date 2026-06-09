"use client";

import styles from "./WeightEditor.module.css";
import type { Weight } from "@/types";

type Props = {
  weights: Weight;
  onChange: (weights: Weight) => void;
};

const fields: Array<{ key: keyof Weight; label: string; hint: string }> = [
  { key: "issue", label: "Issue 重み", hint: "解決済みIssueの起票・対応" },
  { key: "pr", label: "PR 重み", hint: "マージされたPRの規模・件数" },
  { key: "review", label: "Review 重み", hint: "他メンバーへのレビュー" },
  { key: "tat", label: "TAT 重み", hint: "リードタイム・反応速度" },
  { key: "sp", label: "SP 重み", hint: "ストーリーポイントラベル" },
];

export function WeightEditor({ weights, onChange }: Props) {
  return (
    <div className={styles.wrapper}>
      {fields.map((f) => (
        <div key={f.key} className={styles.row}>
          <div className={styles.head}>
            <div className={styles.labelGroup}>
              <span className={styles.label}>{f.label}</span>
              <span className={styles.hint}>{f.hint}</span>
            </div>
            <span className={styles.value}>×{weights[f.key].toFixed(1)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={4}
            step={0.1}
            value={weights[f.key]}
            onChange={(e) =>
              onChange({ ...weights, [f.key]: Number(e.target.value) })
            }
            className={styles.slider}
          />
        </div>
      ))}
    </div>
  );
}
