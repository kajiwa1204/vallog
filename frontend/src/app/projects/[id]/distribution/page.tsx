"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { AllocationTable } from "@/features/distribution/AllocationTable";
import { CreateProposalDialog } from "@/features/distribution/CreateProposalDialog";
import { EditHistoryTimeline } from "@/features/distribution/EditHistoryTimeline";
import { ProposalRecords } from "@/features/distribution/ProposalRecords";
import { ProposalCompare } from "@/features/distribution/ProposalCompare";
import { ProposalSwitcher } from "@/features/distribution/ProposalSwitcher";
import { ScorePanel } from "@/features/distribution/ScorePanel";
import { SummaryPanel } from "@/features/distribution/SummaryPanel";
import { useDistribution } from "@/features/distribution/useDistribution";
import { DistributionWeightEditor } from "@/features/distribution/WeightEditor";
import { useAuth } from "@/hooks/useAuth";
import { useProject } from "@/hooks/useProject";
import styles from "./page.module.css";

/**
 * 分配シミュレーション（画面7）。
 *
 * **スコアが現れる唯一の画面**（docs/scoring_design.md「Goodhart対策とスコアの事後
 * 開示」）。縦の並びがそのまま議論の順序になっている:
 *
 *   概観（スコアからメンバーごとの記録へ辿れる）
 *     → 分配案（人が決める）
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
 * 根拠となる個別の記録は画面5へ分ける。画面4と同じチーム変化ログを重複表示せず、
 * スコア行から該当メンバーの記録へ1クリックで辿れるようにする。
 */
export default function DistributionPage() {
  const { id } = useParams<{ id: string }>();
  // リダイレクトは AppShell 側の useAuth が担う。ここは認証確定を待つだけ
  const { status } = useAuth({ required: false });
  const authed = status === "authenticated";
  const [confirmingCreate, setConfirmingCreate] = useState(false);

  const { project } = useProject(id, authed);
  const {
    proposals,
    drafts,
    past,
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
    compareIds,
    toggleCompare,
    details,
    detailPending,
    detailErrorById,
    fetchDetail,
    createProposal,
    updateItems,
    updateProposal,
    finalize,
    deleteProposal,
    reload,
  } = useDistribution(id, authed);

  const hasProposals = proposals.length > 0;

  /**
   * 貢献サマリーが1件でもあるか。無いときは概観を2カラムにしない。
   *
   * 「スコアと貢献サマリーを同列に置く」はレイアウトで主張したことなので、片方が空だと
   * 主張が見た目で崩れる（実測でスコア758px に対しサマリー170px、右が588px空く）。
   * 生成はまだ #16 の担当で、1件も無いチームのほうが多い。
   */
  // **読み込み中（null）を「0件」と同じ扱いにしない。** summaries は非同期に埋まるので、
  // null を0件と見なすとサマリーを持つチームでは毎回 1カラム→2カラム の切り替えが起き、
  // スコアカードの幅が変わって全メンバーのバーが引き直される
  const singleColumn = summaries !== null && summaries.length === 0;

  /**
   * 案を作る操作がスコアの開示スイッチを兼ねているかどうか。
   *
   * すでに開示されている（他に検討中の案がある）なら、作っても開示状態は変わらない。
   * そのときに「これ以降スコアが表示されます」と出すのは事実に反するので、その節だけ
   * 出さない。ダイアログ自体は名前と報酬総額を受け取るので常に開く。
   */
  const createWillDiscloseScores = scoreState.kind === "undisclosed";

  /**
   * 選択中の案は検討中なのにスコアが非開示＝最終更新から30日を過ぎている（#100）。
   *
   * 案が確定済みでも0件でもないのに閉じている、という条件からしか判定できない。
   * APIは理由まで返さないが、画面は選択中の案の状態を知っているので言い分けられる。
   */
  const disclosureLapsed =
    proposal !== null &&
    !proposal.finalized &&
    scoreState.kind === "undisclosed";

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
          loading={listLoading}
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
            ダッシュボードの変化ログを読み、チームで話してから分配案を作ります。
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
          <ErrorState message={listError} onRetry={reload} retrying={listLoading} />
        </Card>
      ) : listLoading && !hasProposals ? (
        <Card>
          <Spinner label="分配案を読み込んでいます…" />
        </Card>
      ) : hasProposals ? (
        <ProposalSwitcher
          drafts={drafts}
          selectedId={selectedId}
          onSelect={selectProposal}
          onCreate={() => setConfirmingCreate(true)}
          comparing={comparing}
          onToggleCompare={() => setComparing(!comparing)}
          canCompare={proposals.length > 1}
          creating={saving}
        />
      ) : (
        <div className={styles.createRow}>
          <Button loading={saving} onClick={() => setConfirmingCreate(true)}>
            分配案を作成する
          </Button>
          {saveError && <ErrorState message={saveError} />}
        </div>
      )}

      {comparing && (
        <ProposalCompare
          options={proposals}
          selectedIds={compareIds}
          onToggle={toggleCompare}
          details={details}
          pendingIds={detailPending}
          errorById={detailErrorById}
          onRetry={fetchDetail}
        />
      )}

      {/* 概観。数値（スコアと生事実）と文章（貢献サマリー）を同列に並べる。
          どちらも同じ活動を別の粒度で言い直したものなので、片方を先に読ませる理由が
          ない。横に置くと「なぜこの数字なのか」をその場で照らし合わせられる */}
      <div className={`${styles.overview} ${singleColumn ? styles.singleColumn : ""}`}>
        <ScorePanel
          projectId={id}
          state={scoreState}
          onRetry={reloadScores}
          selectedIsFinalized={proposal?.finalized ?? false}
          disclosureLapsed={disclosureLapsed}
          hasFinalized={past.length > 0}
        />
        <SummaryPanel
          projectId={id}
          repoOwner={project?.repo_owner}
          repoName={project?.repo_name}
          summaries={summaries}
        />
      </div>

      {detailError ? (
        <Card title="分配案">
          <ErrorState
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
              disclosureLapsed={disclosureLapsed}
              onFinalize={() => finalize(proposal.id)}
              onDelete={() => deleteProposal(proposal.id)}
            />
          </>
        )
      )}

      {/* 確定した分配と削除された案の記録。もう触れないので、いま触る案とは面を
          分けて畳む。削除も残すのは、痕跡が消えると #100 の抑止の根拠が無くなるため */}
      <ProposalRecords
        items={past}
        details={details}
        pendingIds={detailPending}
        errorById={detailErrorById}
        onOpen={fetchDetail}
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

      <CreateProposalDialog
        open={confirmingCreate}
        onClose={() => setConfirmingCreate(false)}
        creating={saving}
        willDiscloseScores={createWillDiscloseScores}
        onConfirm={async (name, totalAmount) => {
          if (await createProposal(name, totalAmount)) setConfirmingCreate(false);
        }}
      />
    </AppShell>
  );
}
