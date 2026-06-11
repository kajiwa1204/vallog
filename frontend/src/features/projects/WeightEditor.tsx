"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { CATEGORIES } from "@/constants";
import type { CategoryWeights } from "@/types";
import styles from "./WeightEditor.module.css";

type Props = {
  weights: CategoryWeights;
  saving: boolean;
  onSave: (weights: CategoryWeights) => void;
};

// プロジェクトのデフォルト重み。分配案ごとの重みとは独立して保持される
export function WeightEditor({ weights, saving, onSave }: Props) {
  const [draft, setDraft] = useState<CategoryWeights>(weights);

  useEffect(() => {
    setDraft(weights);
  }, [weights]);

  const total = draft.activity + draft.speed + draft.quality;
  const dirty =
    draft.activity !== weights.activity ||
    draft.speed !== weights.speed ||
    draft.quality !== weights.quality;

  return (
    <div className={styles.wrap}>
      <div className={styles.bar}>
        {CATEGORIES.map((c) => (
          <span
            key={c.key}
            className={styles.barSegment}
            style={{
              flexGrow: draft[c.key],
              background: c.color,
            }}
          >
            {draft[c.key] >= 12 && (
              <span className={`num ${styles.barLabel}`}>{draft[c.key]}%</span>
            )}
          </span>
        ))}
      </div>

      <div className={styles.rows}>
        {CATEGORIES.map((c) => (
          <label key={c.key} className={styles.row}>
            <span className={styles.label}>
              <span className={styles.swatch} style={{ background: c.color }} />
              {c.label}
            </span>
            <input
              className={styles.slider}
              type="range"
              min={0}
              max={100}
              step={5}
              value={draft[c.key]}
              onChange={(e) =>
                setDraft((prev) => ({
                  ...prev,
                  [c.key]: parseInt(e.target.value, 10),
                }))
              }
              style={{ accentColor: c.color }}
            />
            <input
              className={`num ${styles.numInput}`}
              type="number"
              min={0}
              max={100}
              value={draft[c.key]}
              onChange={(e) =>
                setDraft((prev) => ({
                  ...prev,
                  [c.key]: parseInt(e.target.value, 10) || 0,
                }))
              }
            />
          </label>
        ))}
      </div>

      <div className={styles.footer}>
        <span
          className={`num ${styles.total} ${total !== 100 ? styles.invalid : ""}`}
        >
          合計 {total}%{total !== 100 && "（100%にしてください）"}
        </span>
        <Button
          size="s"
          disabled={!dirty || total !== 100}
          loading={saving}
          onClick={() => onSave(draft)}
        >
          重みを保存
        </Button>
      </div>
    </div>
  );
}
