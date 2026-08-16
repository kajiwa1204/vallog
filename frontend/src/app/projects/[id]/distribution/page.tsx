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
 * 開示」）。縦の並びがそのまま議論の順序になっている:
 *
 *   概観（スコアと貢献サマリーを同列に並べる）
 *     → 分配案（人が決める）
 *     → 変化ログ（根拠を1件ずつ確かめる）
 *     → 重み・編集履歴
 *
 * スコアと貢献サマリーを横並びの同列に置くのは、**どちらも同じ活動を別の粒度で
 * 言い直したもの**で、片方だけを先に読ませる理由がないため。数値の隣に文章があると
 * 「なぜこの数字なのか」をその場で照らし合わせられる。
 *
 * 以前はスコアを最下部に小さく置いていた（「数字の降格」）が、**その役目は #100 の
 * 開示ゲートが引き継いだ**。作業期間中はAPIがスコアを返さないので、③事前既知を折る
 * 担保はページ内の位置ではなく構造の側にある。開示が許された文脈での配置は、位置で
 * 守る必要がなくなった分だけ読みやすさに寄せてよい。
 *
 * 一方 ①ターゲット（スコアがそのまま分配額になる）への対策は位置とは無関係に効かせる
 * 必要があり、これは「分配の最終決定は人間」＝手動調整と理由必須の側が担う。
 *
 * 変化ログは高さに上限を掛けて内部スクロールにしてある。ここを伸びるままにすると、
 * この画面で実際にやること（配分を決める）に着くまでのスクロールが長くなりすぎる。
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
            下の変化ログを読み、チームで話してから分配案を作ります。
          </p>
          <p className={styles.introBody}>
            案を作ると、GitHubのスコアから計算した割合が出発点として入ります。そこから全員が自由に調整でき、
            調整には理由の入力が必要です。変更はすべて記録され、チームの全員が見られます。
            {/* 案が0件のいまはスコア欄が「分配案を作成すると表示されます」になっている。
                なぜそう出ているのかを、その場所とセットで言う */}
            スコアは案を作るまで表示されません。
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

      {/* 概観。数値（スコアと生事実）と文章（貢献サマリー）を同列に並べる。
          どちらも同じ活動を別の粒度で言い直したものなので、片方を先に読ませる理由が
          ない。横に置くと「なぜこの数字なのか」をその場で照らし合わせられる */}
      <div className={styles.overview}>
        <ScorePanel
          state={scoreState}
          onRetry={reloadScores}
          selectedIsFinalized={proposal?.finalized ?? false}
        />
        <SummaryPanel summaries={summaries} />
      </div>

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
          </>
        )
      )}

      {/* 根拠。上の概観で見た数字が実際に何から来ているかを1件ずつ確かめる場所。
          案の有無に関わらず常に出す（案を作る前の議論もここを読んで始まる） */}
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

      {proposal && (
        <>
          <DistributionWeightEditor
            proposal={proposal}
            saving={saving}
            onSave={(weights, reason) =>
              updateProposal(proposal.id, { reason, weights })
            }
          />

          <EditHistoryTimeline logs={proposal.edit_logs} />
        </>
      )}
      </div>
    </AppShell>
  );
}
