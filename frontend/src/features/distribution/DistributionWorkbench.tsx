"use client";

import { useState } from "react";
import styles from "./DistributionWorkbench.module.css";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { WeightEditor } from "./WeightEditor";
import { AllocationTable } from "./AllocationTable";
import { EditHistoryTimeline } from "./EditHistoryTimeline";
import { useDistribution } from "./useDistribution";
import { formatYen, mockScores } from "@/lib/mockData";

export function DistributionWorkbench() {
  const {
    totalReward,
    setTotalReward,
    weights,
    setWeights,
    preview,
    overrides,
    applyOverride,
    clearOverride,
    resetAllOverrides,
    editLog,
    proposals,
    savedPreviews,
    saveProposal,
    loadProposal,
  } = useDistribution();

  const [proposalName, setProposalName] = useState("");
  const previewTotal = preview.items.reduce(
    (acc, i) => acc + (i.manualOverride ?? i.amount),
    0,
  );
  const overrideCount = Object.keys(overrides).length;
  const delta = previewTotal - totalReward;

  const handleSave = () => {
    if (!proposalName.trim()) return;
    saveProposal(proposalName.trim());
    setProposalName("");
  };

  return (
    <div className={styles.layout}>
      <div className={styles.colMain}>
        <Card
          title={
            <span className={styles.previewTitle}>
              現在の分配案 <Badge tone="accent">編集可能</Badge>
            </span>
          }
          actions={
            <div className={styles.previewActions}>
              {overrideCount > 0 && (
                <Button size="sm" variant="ghost" onClick={resetAllOverrides}>
                  すべての手動調整を解除
                </Button>
              )}
              <div className={styles.previewTotalArea}>
                <div className={styles.previewTotalLabel}>合計</div>
                <div className={styles.previewTotalValue}>{formatYen(previewTotal)}</div>
                {delta !== 0 && (
                  <div
                    className={[
                      styles.delta,
                      delta > 0 ? styles.deltaUp : styles.deltaDown,
                    ].join(" ")}
                  >
                    予算 {formatYen(totalReward)} に対し {delta > 0 ? "+" : "−"}
                    {formatYen(Math.abs(delta))}
                  </div>
                )}
              </div>
            </div>
          }
        >
          {overrideCount > 0 && (
            <div className={styles.manualNotice}>
              ⚠ {overrideCount}名分の金額が手動で調整されています。理由は下の編集履歴に全員公開で記録されています。
            </div>
          )}
          <AllocationTable
            items={preview.items}
            editable
            onApplyOverride={applyOverride}
            onClearOverride={clearOverride}
          />
        </Card>

        <Card title="編集履歴（全員公開）">
          <EditHistoryTimeline logs={editLog} />
        </Card>
      </div>

      <div className={styles.colSide}>
        <Card title="総報酬額">
          <div className={styles.totalInputRow}>
            <span className={styles.yenMark}>¥</span>
            <input
              type="number"
              value={totalReward}
              onChange={(e) => setTotalReward(Number(e.target.value) || 0)}
              className={styles.totalInput}
            />
          </div>
          <div className={styles.totalHint}>{formatYen(totalReward)}</div>
        </Card>

        <Card title={<span className={styles.auxTitle}>スコアの重み <Badge tone="muted">補助</Badge></span>}>
          <p className={styles.auxLead}>
            自動計算の比率を変えたいときに使います。最終的な金額は下記テーブルで個別に調整できます。
          </p>
          <WeightEditor weights={weights} onChange={setWeights} />
        </Card>

        <Card title={<span className={styles.auxTitle}>GitHubスコア <Badge tone="muted">補助</Badge></span>}>
          <ul className={styles.scoreList}>
            {[...mockScores]
              .sort((a, b) => b.total - a.total)
              .map((s) => (
                <li key={s.login}>
                  <span className={styles.scoreName}>{s.name}</span>
                  <span className={styles.scoreValue}>{s.total} pts</span>
                </li>
              ))}
          </ul>
        </Card>

        <Card title="この案を保存">
          <div className={styles.saveBlock}>
            <input
              type="text"
              placeholder="例: 案C: レビュー貢献を反映"
              value={proposalName}
              onChange={(e) => setProposalName(e.target.value)}
              className={styles.saveInput}
            />
            <Button onClick={handleSave} disabled={!proposalName.trim()}>
              保存
            </Button>
          </div>
        </Card>
      </div>

      <div className={styles.fullWidth}>
        <h3 className={styles.proposalsTitle}>保存された案（比較）</h3>
        <div className={styles.proposalsGrid}>
          {proposals.map((p, idx) => {
            const distribution = savedPreviews[idx];
            const overrideCount = Object.keys(p.overrides).length;
            return (
              <Card
                key={p.id}
                title={p.name}
                actions={
                  <Button size="sm" variant="ghost" onClick={() => loadProposal(p.id)}>
                    この案を読み込む
                  </Button>
                }
              >
                <div className={styles.proposalMeta}>
                  <span>総額 {formatYen(p.totalReward)}</span>
                  <span>
                    重み Issue×{p.weights.issue} PR×{p.weights.pr} Review×{p.weights.review}
                  </span>
                  {overrideCount > 0 && (
                    <Badge tone="warn">手動調整 {overrideCount}名</Badge>
                  )}
                </div>
                <AllocationTable items={distribution.items} />
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
