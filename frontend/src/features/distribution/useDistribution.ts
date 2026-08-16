"use client";

import { useCallback, useEffect, useState } from "react";
import { useChangeLog } from "@/hooks/useChangeLog";
import { ApiError, api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type {
  CategoryWeights,
  Proposal,
  ProposalListItem,
  ScoreResponse,
  Summary,
} from "@/types";
import { toRatioString, type AllocationRow } from "./allocation";

// GitHub由来の失敗は services/github.py が全部 502 に写すので、ステータスだけでは
// 原因を切り分けられない。分配の操作（案の作成・重み変更）は内部でスコア計算＝同期を
// 通るため、変化ログと同じ出し分けが要る（AGENTS.md「code 基準で出し分ける」）
const GITHUB_MESSAGES = {
  REPO_NOT_FOUND:
    "GitHubリポジトリを読み取れませんでした。リポジトリへのアクセス権限を確認してください。",
  GITHUB_RATE_LIMITED:
    "GitHubの利用上限に達しました。しばらく待つと自動で解除されます。",
  GITHUB_FORBIDDEN:
    "GitHubがアクセスを拒否しました（利用上限の可能性があります）。しばらく待ってから開き直してください。",
  GITHUB_AUTH_FAILED: "GitHubとの連携が切れています。ログインし直してください。",
  GITHUB_TIMEOUT: "GitHubの応答がありませんでした。",
  GITHUB_UNAVAILABLE: "GitHubが応答していません。",
} as const;

/**
 * 比較に同時に並べられる案の数。横に並べて読める限界で切る。
 * 上限が無いと、案が数十件あるチームで列が数十本のテーブルが出る（読めないうえ、
 * その数だけ詳細を取りに行くことになる）。
 */
export const MAX_COMPARE = 4;

/**
 * スコアの開示状態。「取得できなかった」と「まだ見せない」を型で分ける。
 *
 * 検討中の案が無いとき /scores は 403 を返すが、これは**設計どおりの正常な状態**
 * （#100）であって失敗ではない。同じ null に潰すと、画面はエラーとして赤く出すか、
 * 黙って何も出さないかしか選べなくなる。
 */
export type ScoreState =
  | { kind: "loading" }
  | { kind: "ready"; scores: ScoreResponse }
  | { kind: "undisclosed" }
  | { kind: "error"; message: string; retryable: boolean };

export function useDistribution(projectId: string, enabled = true) {
  // 主役の変化ログ。全メンバー分を出すので member は渡さない（絞り込みチップも置かない）
  const changelog = useChangeLog(projectId, { enabled });

  const [proposals, setProposals] = useState<ProposalListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  // 保存系（作成・調整・重み変更・確定）の進行と失敗。読み取りとは分けて持つ。
  // 混ぜると、保存に失敗しただけで一覧が消えたように見える
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [scoreState, setScoreState] = useState<ScoreState>({ kind: "loading" });
  // スコアを計算するときの重み。選択中の案の重みを使う（null ならプロジェクト既定）
  const [scoreWeights, setScoreWeights] = useState<CategoryWeights | null>(null);
  const [summaries, setSummaries] = useState<Summary[] | null>(null);

  /**
   * 触る対象は検討中の案だけ。確定済みは編集も削除もできないので、切り替えバーには
   * 出さず履歴として別に置く（分配を何度もまわすチームでは確定済みが溜まり続け、
   * 検討中の案がその中に埋もれる）。
   */
  const drafts = proposals.filter((p) => !p.finalized && p.deleted_at === null);
  // 分配の記録（確定済み・削除済み）。新しい出来事から読む
  const past = proposals
    .filter((p) => p.finalized || p.deleted_at !== null)
    .sort((a, b) =>
      ((b.finalized_at ?? b.deleted_at) ?? "").localeCompare(
        (a.finalized_at ?? a.deleted_at) ?? "",
      ),
    );

  const loadProposals = useCallback(async () => {
    if (!enabled) return;
    setListLoading(true);
    setListError(null);
    try {
      // 削除済みも取る。作業対象の一覧からは外すが、記録としては読める必要がある
      const data = await api.get<ProposalListItem[]>(
        `/projects/${projectId}/distributions?include_deleted=true`,
      );
      setProposals(data);
      // 選択は検討中の案から選ぶ。消えていたら（他の人が消した等）先頭の検討中に
      // 戻す。確定直後だけは例外で、確定した案を選んだまま残す（結果を確認できる）
      setSelectedId((current) => {
        const still = data.find((p) => p.id === current && p.deleted_at === null);
        if (still) return current;
        return data.find((p) => !p.finalized && p.deleted_at === null)?.id ?? null;
      });
    } catch (e) {
      setListError(
        messageForError(e, { fallback: "分配案の一覧を取得できませんでした" }),
      );
    } finally {
      setListLoading(false);
    }
  }, [projectId, enabled]);

  const loadProposal = useCallback(
    async (proposalId: string) => {
      setDetailLoading(true);
      setDetailError(null);
      try {
        setProposal(
          await api.get<Proposal>(
            `/projects/${projectId}/distributions/${proposalId}`,
          ),
        );
      } catch (e) {
        setProposal(null);
        setDetailError(
          messageForError(e, {
            codes: { DISTRIBUTION_NOT_FOUND: "この分配案は見つかりませんでした。" },
            fallback: "分配案を取得できませんでした",
          }),
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [projectId],
  );

  /**
   * スコアの取得。403 + SCORES_NOT_DISCLOSED は状態として扱い、エラーにしない。
   *
   * ステータスだけで判定しないのは、403 の既定訳が「この操作を行う権限がありません」
   * で、**権限の問題ではない**この状況に対して誤った原因を主張してしまうため。
   */
  const loadScores = useCallback(async () => {
    if (!enabled) return;
    setScoreState({ kind: "loading" });
    try {
      // 選択中の案の重みで計算させる。案の配分比率は案の重みで算出されるので、
      // スコアだけプロジェクト既定の重みで取ると、同じ画面の「配分」と「その根拠」が
      // 別々の重みの産物になる（重みを 100/0/0 にすると根拠と配分が別の数字を出す）
      const params = new URLSearchParams();
      if (scoreWeights !== null) {
        params.set("weight_activity", String(scoreWeights.activity));
        params.set("weight_speed", String(scoreWeights.speed));
        params.set("weight_quality", String(scoreWeights.quality));
      }
      const query = params.toString();
      const scores = await api.get<ScoreResponse>(
        `/projects/${projectId}/scores${query ? `?${query}` : ""}`,
      );
      setScoreState({ kind: "ready", scores });
    } catch (e) {
      if (e instanceof ApiError && e.code === "SCORES_NOT_DISCLOSED") {
        setScoreState({ kind: "undisclosed" });
        return;
      }
      const code = e instanceof ApiError ? (e.code ?? null) : null;
      setScoreState({
        kind: "error",
        message: messageForError(e, {
          codes: GITHUB_MESSAGES,
          fallback: "スコアを取得できませんでした",
        }),
        // 利用上限に当たっているときに再試行を出すと、押すたびにGitHubを叩いて
        // 状況を悪化させる
        retryable: code !== "GITHUB_RATE_LIMITED" && code !== "GITHUB_FORBIDDEN",
      });
    }
  }, [projectId, enabled, scoreWeights]);

  // 生成済みの貢献サマリー（第2層）。生成の起動・進捗は #16 の担当なのでここでは読むだけ。
  // 失敗しても画面にエラーを出さない。まだ1件も生成していないチームのほうが多く、
  // 主役（変化ログ）には影響がないため、無いなら無いと言えば足りる
  const loadSummaries = useCallback(async () => {
    if (!enabled) return;
    try {
      setSummaries(await api.get<Summary[]>(`/projects/${projectId}/summaries`));
    } catch {
      setSummaries(null);
    }
  }, [projectId, enabled]);

  useEffect(() => {
    loadProposals();
    loadScores();
    loadSummaries();
  }, [loadProposals, loadScores, loadSummaries]);

  useEffect(() => {
    if (selectedId === null) {
      setProposal(null);
      setDetailError(null);
      return;
    }
    loadProposal(selectedId);
  }, [selectedId, loadProposal]);

  // 選択中の案の重みでスコアを計算させる。同じ値なら参照を変えないので、
  // loadScores（scoreWeights に依存）が無限に走ることはない
  useEffect(() => {
    if (proposal === null) {
      setScoreWeights(null);
      return;
    }
    const next = proposal.weights;
    setScoreWeights((current) =>
      current !== null &&
      current.activity === next.activity &&
      current.speed === next.speed &&
      current.quality === next.quality
        ? current
        : next,
    );
  }, [proposal]);

  /**
   * 保存系の共通処理。**成功したら必ずスコアの開示状態を取り直す。**
   *
   * 最初の案を作った瞬間に開示され、最後の案を確定した瞬間に非開示へ戻るのが #100 の
   * 仕様なので、案の状態を変える操作はすべてスコアの見え方を変える。ここを一箇所に
   * まとめないと、「確定したのにスコアが残っている」画面が作れてしまう。
   */
  const mutate = useCallback(
    async (run: () => Promise<Proposal>) => {
      setSaving(true);
      setSaveError(null);
      try {
        const updated = await run();
        setProposal(updated);
        // 配分が変わったら履歴・比較のキャッシュは古い。持ち越すと同じ案の
        // 違う数字が同じ画面に並ぶ
        setDetails({});
        setSelectedId(updated.id);
        await Promise.all([loadProposals(), loadScores()]);
        return true;
      } catch (e) {
        setSaveError(
          messageForError(e, {
            codes: {
              ...GITHUB_MESSAGES,
              DISTRIBUTION_FINALIZED:
                "この案は確定済みのため編集できません。新しい案を作成してください。",
              DISTRIBUTION_NO_MEMBERS:
                "分配対象のメンバーがいません。GitHubの同期が終わっているか確認してください。",
              DISTRIBUTION_RATIO_TOTAL_INVALID:
                "配分の合計が100%になっていません。",
            },
            fallback: "保存できませんでした",
          }),
        );
        return false;
      } finally {
        setSaving(false);
      }
    },
    [loadProposals, loadScores],
  );

  const createProposal = useCallback(
    (name?: string, totalAmount?: string) =>
      // items を送らないとスコアから初期比率が算出される。案の出発点は
      // 「スコアどおりの配分」で、そこから議論して動かす
      mutate(() =>
        api.post<Proposal>(`/projects/${projectId}/distributions`, {
          ...(name ? { name } : {}),
          // 空文字は数値として不正なので送らない（未入力＝割合のみ表示）
          ...(totalAmount ? { total_amount: totalAmount } : {}),
        }),
      ),
    [projectId, mutate],
  );

  const updateItems = useCallback(
    (proposalId: string, rows: AllocationRow[], reason: string) =>
      mutate(() =>
        api.patch<Proposal>(
          `/projects/${projectId}/distributions/${proposalId}/items`,
          {
            reason,
            items: rows.map((row) => ({
              github_login: row.github_login,
              ratio: toRatioString(row.tenths),
            })),
          },
        ),
      ),
    [projectId, mutate],
  );

  const updateProposal = useCallback(
    (
      proposalId: string,
      payload: { reason: string; name?: string; total_amount?: string; weights?: CategoryWeights },
    ) =>
      mutate(() =>
        api.patch<Proposal>(
          `/projects/${projectId}/distributions/${proposalId}`,
          payload,
        ),
      ),
    [projectId, mutate],
  );

  const finalize = useCallback(
    (proposalId: string) =>
      mutate(() =>
        api.post<Proposal>(
          `/projects/${projectId}/distributions/${proposalId}/finalize`,
        ),
      ),
    [projectId, mutate],
  );

  /**
   * 検討中の案を削除する。確定済みは 409（合意の記録は消せない）。
   *
   * mutate に載せないのは、削除は Proposal を返さないため。返ってこない案を
   * setProposal してしまうと、消したはずの案が表示に残る。
   */
  const deleteProposal = useCallback(
    async (proposalId: string) => {
      setSaving(true);
      setSaveError(null);
      try {
        await api.delete(`/projects/${projectId}/distributions/${proposalId}`);
        setDetails({});
        setCompareIds((ids) => ids.filter((id) => id !== proposalId));
        // 選択を外してから読み直す。残したままだと詳細の取得が404を返す
        setSelectedId(null);
        setProposal(null);
        // 最後の未確定案を消すとスコアは非開示に戻る。案の状態を変える操作は
        // すべて開示の見え方を変えるので、必ず取り直す
        await Promise.all([loadProposals(), loadScores()]);
        return true;
      } catch (e) {
        setSaveError(
          messageForError(e, {
            codes: {
              DISTRIBUTION_FINALIZED:
                "確定済みの案は削除できません。合意の記録として残ります。",
              DISTRIBUTION_NOT_FOUND: "この分配案は既に削除されています。",
            },
            fallback: "分配案を削除できませんでした",
          }),
        );
        return false;
      } finally {
        setSaving(false);
      }
    },
    [projectId, loadProposals, loadScores],
  );

  /**
   * 案の詳細キャッシュ。確定済みの履歴を開くときと、比較で選んだ案に使う。
   *
   * 一覧は配分値を返さないので案ごとに引き直す必要がある。**要求されたものだけ**を
   * 1件ずつ取るのが要点で、以前は比較を開いた瞬間に全件を並列で取りに行っていた。
   * 分配を何度もまわすチームでは案が数十件に育つので、開いた回数ぶんだけその数の
   * リクエストが飛ぶ。
   *
   * 取得済みは保持して、開き直しや選び直しで投げ直さない。書き込みのたびに捨てる
   * （mutate 側）ので、古い配分が履歴に残ることはない。
   */
  const [details, setDetails] = useState<Record<string, Proposal>>({});
  const [detailPending, setDetailPending] = useState<string[]>([]);
  const [detailErrorById, setDetailErrorById] = useState<Record<string, string>>({});

  const fetchDetail = useCallback(
    async (proposalId: string) => {
      setDetailPending((ids) =>
        ids.includes(proposalId) ? ids : [...ids, proposalId],
      );
      setDetailErrorById(({ [proposalId]: _dropped, ...rest }) => rest);
      try {
        const data = await api.get<Proposal>(
          `/projects/${projectId}/distributions/${proposalId}`,
        );
        setDetails((current) => ({ ...current, [proposalId]: data }));
      } catch (e) {
        setDetailErrorById((current) => ({
          ...current,
          [proposalId]: messageForError(e, {
            fallback: "分配案を取得できませんでした",
          }),
        }));
      } finally {
        setDetailPending((ids) => ids.filter((id) => id !== proposalId));
      }
    },
    [projectId],
  );

  const [comparing, setComparing] = useState(false);
  // 比較に選んだ案。多くても4件までにする（それ以上は横に並べても読めない）
  const [compareIds, setCompareIds] = useState<string[]>([]);

  const toggleCompare = useCallback(
    (proposalId: string) => {
      setCompareIds((ids) =>
        ids.includes(proposalId)
          ? ids.filter((id) => id !== proposalId)
          : ids.length >= MAX_COMPARE
            ? ids
            : [...ids, proposalId],
      );
    },
    [],
  );

  // 選ばれていて、まだ取っていないものだけを取りに行く
  useEffect(() => {
    if (!comparing) return;
    for (const id of compareIds) {
      if (details[id] || detailPending.includes(id) || detailErrorById[id]) continue;
      fetchDetail(id);
    }
  }, [comparing, compareIds, details, detailPending, detailErrorById, fetchDetail]);

  const reload = useCallback(() => {
    loadProposals();
    loadScores();
    loadSummaries();
    changelog.reload();
    if (selectedId !== null) loadProposal(selectedId);
  }, [loadProposals, loadScores, loadSummaries, changelog, selectedId, loadProposal]);

  return {
    changelog,
    proposals,
    drafts,
    past,
    selectedId,
    selectProposal: setSelectedId,
    proposal,
    listError,
    listLoading,
    detailError,
    detailLoading,
    saving,
    saveError,
    clearSaveError: useCallback(() => setSaveError(null), []),
    scoreState,
    reloadScores: loadScores,
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
  };
}
