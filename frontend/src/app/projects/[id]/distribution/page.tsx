"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { AllocationTable } from "@/features/distribution/AllocationTable";
import { ChangeLogPanel } from "@/features/distribution/ChangeLogPanel";
import { EditHistoryTimeline } from "@/features/distribution/EditHistoryTimeline";
import { PanelError } from "@/features/distribution/PanelError";
import { ProposalCompare } from "@/features/distribution/ProposalCompare";
import { ProposalSwitcher } from "@/features/distribution/ProposalSwitcher";
import { ScorePanel } from "@/features/distribution/ScorePanel";
import { SummaryPanel } from "@/features/distribution/SummaryPanel";
import { useDistribution } from "@/features/distribution/useDistribution";
import { DistributionWeightEditor } from "@/features/distribution/WeightEditor";
import { useAuth } from "@/hooks/useAuth";
import { isRetryableChangeLogError } from "@/hooks/useChangeLog";
import { useProject } from "@/hooks/useProject";
import styles from "./page.module.css";

/**
 * 分配シミュレーション（画面7）。
 *
 * **スコアが現れる唯一の画面**（docs/scoring_design.md「Goodhart対策とスコアの事後
 * 開示」）。ただし主役は上部の変化ログで、スコアは最下部に補助情報として置く。
 * ページの縦の並びがそのまま議論の順序になっている:
 *
 *   変化ログ（事実）→ 貢献サマリー（要約）→ 分配案（人が決める）→ スコア（補助）
 *
 * この順序は #100 のゲートで構造的にも強制されている。案を作るまでスコアは返らない
 * ので、最初に開いたときは最下部のカードが「分配案を作成すると表示されます」になる。
 */
export default function DistributionPage() {
  const { id } = useParams<{ id: string }>();
  // リダイレクトは AppShell 側の useAuth が担う。ここは認証確定を待つだけ
  const { status } = useAuth({ required: false });
  const authed = status === "authenticated";

  const { project } = useProject(id, authed);
  const {
    changelog,
    proposals,
    selectedId,
    selectProposal,
    proposal,
    listError,
    listLoading,
    detailError,
    detailLoading,
    saving,
    saveError,
    scoreState,
    reloadScores,
    summaries,
    comparing,
    setComparing,
    compared,
    compareError,
    reloadCompare,
    createProposal,
    updateItems,
    updateProposal,
    finalize,
    reload,
  } = useDistribution(id, authed);

  const hasProposals = proposals.length > 0;

  return (
    <AppShell projectId={id} projectName={project?.name}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>分配シミュレーション</h1>
          <p className={styles.subtitle}>
            チームの記録を読みながら、分配の割合を話し合って決めます。
          </p>
        </div>
        <Button
          variant="secondary"
          size="s"
          onClick={reload}
          loading={listLoading || changelog.loading}
        >
          再読み込み
        </Button>
      </header>

      {/* カード同士の間隔はここで一括して持つ。各カードが自分の外側の余白を
          持つと、並び順を変えたときに間隔が崩れる */}
      <div className={styles.stack}>
      {/* 案が1件も無いときだけ、この画面の使い方を言う。作った後は邪魔になる */}
      {!listLoading && !hasProposals && (
        <div className={styles.intro}>
          <p className={styles.introLead}>
            まず下の変化ログを読み、チームで話してから分配案を作ります。
          </p>
          <p className={styles.introBody}>
            案を作ると、GitHubのスコアから計算した割合が出発点として入ります。そこから全員が自由に調整でき、
            調整には理由の入力が必要です。変更はすべて記録され、チームの全員が見られます。
            スコアは案を作ってから、この画面の最下部にだけ表示されます。
          </p>
        </div>
      )}

      {listError ? (
        <Card title="分配案">
          <PanelError message={listError} onRetry={reload} retrying={listLoading} />
        </Card>
      ) : listLoading && !hasProposals ? (
        <Card>
          <Spinner label="分配案を読み込んでいます…" />
        </Card>
      ) : hasProposals ? (
        <ProposalSwitcher
          proposals={proposals}
          selectedId={selectedId}
          onSelect={selectProposal}
          onCreate={() => createProposal()}
          comparing={comparing}
          onToggleCompare={() => setComparing(!comparing)}
          creating={saving}
        />
      ) : (
        <div className={styles.createRow}>
          <Button loading={saving} onClick={() => createProposal()}>
            分配案を作成する
          </Button>
          {saveError && <PanelError message={saveError} />}
        </div>
      )}

      {comparing && (
        <ProposalCompare
          proposals={compared}
          error={compareError}
          onRetry={reloadCompare}
        />
      )}

      {/* 主役は変化ログ。案の有無に関わらず常に出す（読んでから議論するため） */}
      <ChangeLogPanel
        entries={changelog.entries}
        loading={changelog.loading}
        error={changelog.error}
        hasMore={changelog.hasMore}
        atLimit={changelog.atLimit}
        onLoadMore={changelog.loadMore}
        // 利用上限に当たっているときは再試行を出さない。押すと ensure_synced 経由で
        // またGitHubを叩き、状況を悪化させるだけになる
        onRetry={
          isRetryableChangeLogError(changelog.errorCode)
            ? changelog.reload
            : undefined
        }
      />

      <SummaryPanel summaries={summaries} />

      {detailError ? (
        <Card title="分配案">
          <PanelError
            message={detailError}
            onRetry={() => selectedId && selectProposal(selectedId)}
          />
        </Card>
      ) : detailLoading && proposal === null ? (
        <Card>
          <Spinner label="分配案を読み込んでいます…" />
        </Card>
      ) : (
        proposal && (
          <>
            <AllocationTable
              proposal={proposal}
              saving={saving}
              saveError={saveError}
              onSaveItems={(rows, reason) => updateItems(proposal.id, rows, reason)}
              onSaveTotalAmount={(totalAmount, reason) =>
                updateProposal(proposal.id, { reason, total_amount: totalAmount })
              }
              onFinalize={() => finalize(proposal.id)}
            />

            <DistributionWeightEditor
              proposal={proposal}
              saving={saving}
              onSave={(weights, reason) =>
                updateProposal(proposal.id, { reason, weights })
              }
            />

            <EditHistoryTimeline logs={proposal.edit_logs} />
          </>
        )
      )}

      {/* スコアは最下部。ページの他のどこにも出さない（数字の降格） */}
      <ScorePanel
        state={scoreState}
        onRetry={reloadScores}
        selectedIsFinalized={proposal?.finalized ?? false}
      />
      </div>
    </AppShell>
  );
}
