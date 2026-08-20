"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Input";
import { WeightSliders, weightTotal } from "@/components/ui/WeightSliders";
import type { CategoryWeights, Proposal } from "@/types";
import styles from "./WeightEditor.module.css";

type Props = {
  proposal: Proposal;
  saving: boolean;
  onSave: (weights: CategoryWeights, reason: string) => Promise<boolean>;
};

/**
 * 案ごとのカテゴリ重み（画面7「この画面上でその場で調整・複数案を比較」）。
 *
 * プロジェクトのデフォルト重み（画面3）とは独立して案ごとに持つ。同じGitHubデータに
 * 別の重みを当てた複数案を並べて比較するためで、これが Goodhart の②固定を折る施策に
 * あたる（docs/scoring_design.md）。
 *
 * **重みを変えると配分比率がスコアから再計算され、手動調整は上書きされる。** 重みは
 * 「スコアをどう見るか」の設定なので、変更後は新しい重みで計算し直した値が出発点に
 * 戻るのが正しい。ただし黙って消えると調整した人には事故に見えるので、保存前に言う。
 */
export function DistributionWeightEditor({ proposal, saving, onSave }: Props) {
  const [draft, setDraft] = useState<CategoryWeights>(proposal.weights);
  const [reason, setReason] = useState("");

  useEffect(() => {
    setDraft(proposal.weights);
    setReason("");
  }, [proposal.id, proposal.weights]);

  const total = weightTotal(draft);
  const dirty =
    draft.activity !== proposal.weights.activity ||
    draft.speed !== proposal.weights.speed ||
    draft.quality !== proposal.weights.quality;
  const canSave = dirty && total === 100 && reason.trim().length > 0;

  if (proposal.finalized) {
    return (
      <Card title="カテゴリ重み">
        <WeightSliders
          value={proposal.weights}
          onChange={() => {}}
          disabled
          idPrefix="proposal-weight"
        />
        <p className={styles.locked}>確定済みの案なので変更できません。</p>
      </Card>
    );
  }

  return (
    <Card title="カテゴリ重み">
      <p className={styles.lead}>
        この案だけの重みです。プロジェクトの既定値（画面3）は変わりません。
      </p>

      <WeightSliders value={draft} onChange={setDraft} idPrefix="proposal-weight" />

      <div className={styles.footer}>
        <span className={`num ${styles.total} ${total !== 100 ? styles.invalid : ""}`}>
          合計 {total}%{total !== 100 && "（100%にしてください）"}
        </span>
      </div>

      {dirty && (
        <p className={styles.warning}>
          重みを保存すると、配分比率は新しい重みのスコアから計算し直されます。手動で調整した配分は上書きされます。
        </p>
      )}

      <Textarea
        id="weight-reason"
        label="変更の理由（必須）"
        hint="全員に公開されます。"
        rows={2}
        value={reason}
        disabled={saving}
        onChange={(e) => setReason(e.target.value)}
      />

      <div className={styles.actions}>
        <Button
          disabled={!canSave}
          loading={saving}
          onClick={async () => {
            if (await onSave(draft, reason.trim())) setReason("");
          }}
        >
          重みを保存して再計算
        </Button>
        {dirty && (
          <Button
            variant="ghost"
            size="s"
            disabled={saving}
            onClick={() => setDraft(proposal.weights)}
          >
            元に戻す
          </Button>
        )}
      </div>
    </Card>
  );
}
