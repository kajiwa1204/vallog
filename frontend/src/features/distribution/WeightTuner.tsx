"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { CATEGORIES } from "@/constants";
import type { CategoryWeights } from "@/types";
import styles from "./WeightTuner.module.css";

type Props = {
  weights: CategoryWeights;
  locked: boolean;
  onApply: (weights: CategoryWeights) => void;
};

// 重みをその場で調整し、スコアから分配比率を再計算する
export function WeightTuner({ weights, locked, onApply }: Props) {
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
      <div className={styles.sliders}>
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
              disabled={locked}
              onChange={(e) =>
                setDraft((prev) => ({
                  ...prev,
                  [c.key]: parseInt(e.target.value, 10),
                }))
              }
              style={{ accentColor: c.color }}
            />
            <span className={`num ${styles.value}`}>{draft[c.key]}%</span>
          </label>
        ))}
      </div>

      {!locked && (
        <div className={styles.actions}>
          <span
            className={`num ${styles.total} ${
              total !== 100 ? styles.invalid : ""
            }`}
          >
            合計 {total}%
          </span>
          <Button
            size="s"
            variant="secondary"
            disabled={!dirty || total !== 100}
            onClick={() => onApply(draft)}
          >
            スコアから再計算…
          </Button>
        </div>
      )}
    </div>
  );
}
