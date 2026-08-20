"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { WeightSliders, weightTotal } from "@/components/ui/WeightSliders";
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

  const total = weightTotal(draft);
  const dirty =
    draft.activity !== weights.activity ||
    draft.speed !== weights.speed ||
    draft.quality !== weights.quality;

  return (
    <div className={styles.wrap}>
      <WeightSliders value={draft} onChange={setDraft} idPrefix="project-weight" />

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
