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
 * スコアの開示状態。「取得できなかった」と「まだ見せない」を型で分ける。
 *
 * 案が0件のとき /scores は 403 を返すが、これは**設計どおりの正常な状態**（#100）で
 * あって失敗ではない。同じ null に潰すと、画面はエラーとして赤く出すか、黙って
 * 何も出さないかしか選べなくなる。
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
  const [summaries, setSummaries] = useState<Summary[] | null>(null);

  const loadProposals = useCallback(async () => {
    if (!enabled) return;
    setListLoading(true);
    setListError(null);
    try {
      const data = await api.get<ProposalListItem[]>(
        `/projects/${projectId}/distributions`,
      );
      setProposals(data);
      // 選択中の案が消えていたら（他の人が消した等）先頭に戻す。詳細の取得が
      // 404 を返し続ける状態に留まらないようにする
      setSelectedId((current) =>
        current !== null && data.some((p) => p.id === current)
          ? current
          : (data[0]?.id ?? null),
      );
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
      const scores = await api.get<ScoreResponse>(`/projects/${projectId}/scores`);
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
  }, [projectId, enabled]);

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
    (name?: string) =>
      // items を送らないとスコアから初期比率が算出される。案の出発点は
      // 「スコアどおりの配分」で、そこから議論して動かす
      mutate(() =>
        api.post<Proposal>(`/projects/${projectId}/distributions`, {
          ...(name ? { name } : {}),
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
   * 複数案を並べて比較するための詳細。一覧は配分値を返さないので案ごとに引き直す。
   *
   * 開いたときにまとめて取る（案の数だけ並列リクエスト）。案は多くても数件で、
   * 分配APIはGitHubを叩かずDBだけを見るため、まとめても軽い。比較を開いていない
   * 間は1本も投げない。
   */
  const [comparing, setComparing] = useState(false);
  const [compared, setCompared] = useState<Proposal[] | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);

  const loadCompare = useCallback(async () => {
    setCompared(null);
    setCompareError(null);
    try {
      setCompared(
        await Promise.all(
          proposals.map((p) =>
            api.get<Proposal>(`/projects/${projectId}/distributions/${p.id}`),
          ),
        ),
      );
    } catch (e) {
      setCompareError(
        messageForError(e, { fallback: "比較する案を取得できませんでした" }),
      );
    }
  }, [projectId, proposals]);

  useEffect(() => {
    if (!comparing) return;
    loadCompare();
  }, [comparing, loadCompare]);

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
    compared,
    compareError,
    reloadCompare: loadCompare,
    createProposal,
    updateItems,
    updateProposal,
    finalize,
    reload,
  };
}
