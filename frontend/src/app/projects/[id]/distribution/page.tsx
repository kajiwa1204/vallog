"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Spinner } from "@/components/ui/Spinner";
import { useProject } from "@/hooks/useProject";
import { ApiError } from "@/lib/api";
import { useDistribution } from "@/features/distribution/useDistribution";
import { AllocationTable } from "@/features/distribution/AllocationTable";
import { SummaryPanel } from "@/features/distribution/SummaryPanel";
import { EditHistoryTimeline } from "@/features/distribution/EditHistoryTimeline";
import { WeightTuner } from "@/features/distribution/WeightTuner";
import { ReasonModal } from "@/features/distribution/ReasonModal";
import type { CategoryWeights } from "@/types";
import styles from "./page.module.css";

type PendingChange =
  | { kind: "items"; items: { github_login: string; ratio: string }[] }
  | { kind: "weights"; weights: CategoryWeights }
  | { kind: "amount"; total_amount: string };

export default function DistributionPage() {
  const { id } = useParams<{ id: string }>();
  const { project } = useProject(id);
  const {
    proposals,
    selectedId,
    setSelectedId,
    proposal,
    logs,
    summaries,
    loading,
    detailLoading,
    error,
    createProposal,
    update,
    agree,
  } = useDistribution(id);

  const [newOpen, setNewOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newAmount, setNewAmount] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [pending, setPending] = useState<PendingChange | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [amountDraft, setAmountDraft] = useState<string | null>(null);
  const [agreeing, setAgreeing] = useState(false);

  const locked = proposal?.status === "agreed";

  const handleCreate = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      await createProposal(newTitle, newAmount || null);
      setNewOpen(false);
      setNewTitle("");
      setNewAmount("");
    } catch (e) {
      setCreateError(
        e instanceof ApiError ? e.message : "作成に失敗しました",
      );
    } finally {
      setCreating(false);
    }
  };

  const handleReasonSubmit = async (reason: string) => {
    if (!pending) return;
    setSaving(true);
    setSaveError(null);
    try {
      if (pending.kind === "items") {
        await update({ reason, items: pending.items });
      } else if (pending.kind === "weights") {
        await update({ reason, weights: pending.weights });
      } else {
        await update({ reason, total_amount: pending.total_amount });
      }
      setPending(null);
      setAmountDraft(null);
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell projectId={id} projectName={project?.name}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>分配シミュレーション</h1>
          <p className={styles.subtitle}>
            まず貢献サマリーを読んで議論し、スコアは補助情報として参照してください。
            分配の決定はチームが行います。
          </p>
        </div>
        <Button onClick={() => setNewOpen(true)}>新しい分配案</Button>
      </header>

      {loading ? (
        <Spinner />
      ) : error ? (
        <Card>
          <p className={styles.error}>{error}</p>
        </Card>
      ) : proposals.length === 0 ? (
        <Card>
          <div className={styles.empty}>
            <p>まだ分配案がありません。</p>
            <p className={styles.emptyHint}>
              現在のスコアを初期値として分配案を作成し、チームで調整・合意できます。
            </p>
            <Button onClick={() => setNewOpen(true)}>
              スコアから分配案を作成
            </Button>
          </div>
        </Card>
      ) : (
        <>
          <div className={styles.tabs} role="tablist">
            {proposals.map((p) => (
              <button
                key={p.id}
                role="tab"
                aria-selected={p.id === selectedId}
                className={`${styles.tab} ${
                  p.id === selectedId ? styles.tabActive : ""
                }`}
                onClick={() => setSelectedId(p.id)}
              >
                <span className={styles.tabTitle}>{p.title}</span>
                {p.status === "agreed" ? (
                  <Badge tone="green">合意済み</Badge>
                ) : (
                  <Badge>検討中</Badge>
                )}
              </button>
            ))}
          </div>

          {detailLoading || !proposal ? (
            <Spinner />
          ) : (
            <div className={styles.stack}>
              <Card title="貢献サマリー" padding="m">
                <SummaryPanel projectId={id} summaries={summaries} />
              </Card>

              <Card
                title="分配比率"
                actions={
                  <div className={styles.allocActions}>
                    {amountDraft === null ? (
                      <span className={styles.amountView}>
                        報酬総額:{" "}
                        <span className="num">
                          {proposal.total_amount !== null
                            ? `¥${parseFloat(
                                proposal.total_amount,
                              ).toLocaleString()}`
                            : "未入力"}
                        </span>
                        {!locked && (
                          <Button
                            variant="ghost"
                            size="s"
                            onClick={() =>
                              setAmountDraft(proposal.total_amount ?? "")
                            }
                          >
                            編集
                          </Button>
                        )}
                      </span>
                    ) : (
                      <span className={styles.amountEdit}>
                        <input
                          className={`num ${styles.amountInput}`}
                          type="number"
                          min={0}
                          placeholder="500000"
                          value={amountDraft}
                          onChange={(e) => setAmountDraft(e.target.value)}
                        />
                        <Button
                          size="s"
                          disabled={!amountDraft}
                          onClick={() =>
                            setPending({
                              kind: "amount",
                              total_amount: amountDraft,
                            })
                          }
                        >
                          保存…
                        </Button>
                        <Button
                          variant="ghost"
                          size="s"
                          onClick={() => setAmountDraft(null)}
                        >
                          取消
                        </Button>
                      </span>
                    )}
                  </div>
                }
              >
                <AllocationTable
                  proposal={proposal}
                  onSave={(items) => setPending({ kind: "items", items })}
                />
              </Card>

              <div className={styles.twoCol}>
                <Card title="評価の重み（この案のスコア参照用）">
                  <WeightTuner
                    weights={proposal.weights}
                    locked={!!locked}
                    onApply={(weights) =>
                      setPending({ kind: "weights", weights })
                    }
                  />
                </Card>

                <Card title="編集履歴">
                  <EditHistoryTimeline logs={logs} />
                </Card>
              </div>

              <div className={styles.agreeBar}>
                {locked ? (
                  <p className={`num ${styles.agreedNote}`}>
                    {proposal.agreed_at &&
                      `この分配案は ${new Date(
                        proposal.agreed_at,
                      ).toLocaleString("ja-JP")} にチームで合意されました`}
                  </p>
                ) : (
                  <>
                    <p className={styles.agreeNote}>
                      合意すると、この分配案は編集できなくなり、記録として永続化されます。
                    </p>
                    <Button
                      loading={agreeing}
                      onClick={async () => {
                        setAgreeing(true);
                        try {
                          await agree();
                        } finally {
                          setAgreeing(false);
                        }
                      }}
                    >
                      この案で合意を記録する
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </>
      )}

      <Modal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        title="新しい分配案"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setNewOpen(false)}
              disabled={creating}
            >
              キャンセル
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!newTitle.trim()}
              loading={creating}
            >
              作成する
            </Button>
          </>
        }
      >
        <div className={styles.modalForm}>
          <Input
            label="案のタイトル（必須）"
            placeholder="例: ハッカソン賞金の分配案"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
          />
          <Input
            label="報酬総額（任意・円）"
            type="number"
            min={0}
            placeholder="未入力の場合は割合のみ表示"
            value={newAmount}
            onChange={(e) => setNewAmount(e.target.value)}
          />
          <p className={styles.modalNote}>
            現在のスコアにもとづく分配比率が初期値として設定されます。
          </p>
          {createError && <p className={styles.error}>{createError}</p>}
        </div>
      </Modal>

      <ReasonModal
        open={pending !== null}
        saving={saving}
        error={saveError}
        onClose={() => {
          setPending(null);
          setSaveError(null);
        }}
        onSubmit={handleReasonSubmit}
      />
    </AppShell>
  );
}
