"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import { activeJobStartedAt } from "@/features/summaries/polling";
import { useSummaryPolling } from "@/features/summaries/useSummaryPolling";
import type { PRSummaryItem, Summary, SummaryJob } from "@/types";

export function useMemberSummaries(
  projectId: string,
  login: string,
  enabled = true,
) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [prs, setPrs] = useState<PRSummaryItem[]>([]);
  const [memberJob, setMemberJob] = useState<SummaryJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingMember, setStartingMember] = useState(false);
  const [startingPrs, setStartingPrs] = useState<number[]>([]);
  const [memberUnchanged, setMemberUnchanged] = useState(false);
  const [pollingStopped, setPollingStopped] = useState(false);
  const requestId = useRef(0);
  const memberGenerationBaseline = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    requestId.current += 1;
    memberGenerationBaseline.current = undefined;
    // 動的ルート間の遷移ではコンポーネントが再利用される。前の人の要約を一瞬でも
    // 次の人のものとして出さないよう、識別子が変わった時点で表示データを空にする。
    setSummary(null);
    setPrs([]);
    setMemberJob(null);
    setMemberUnchanged(false);
    setPollingStopped(false);
  }, [projectId, login]);

  const fetchData = useCallback(async () => {
    const currentRequest = ++requestId.current;
    // メンバー一括ジョブの完了を先に観測してから結果を読む。並列だと summaries だけ
    // 完了commit前の値になり、ジョブ完了によってポーリングが止まる競合がある。
    try {
      const jobs = await api.get<SummaryJob[]>(
        `/projects/${projectId}/summary-jobs`,
      );
      const [summaries, prItems] = await Promise.all([
        api.get<Summary[]>(`/projects/${projectId}/summaries`),
        api.get<PRSummaryItem[]>(
          `/projects/${projectId}/summaries/${encodeURIComponent(login)}/prs`,
        ),
      ]);
      if (currentRequest !== requestId.current) return false;

      const nextSummary =
        summaries.find((item) => item.github_login === login) ?? null;
      const nextMemberJob =
        jobs.find((job) => job.github_login === login) ?? null;
      setSummary(nextSummary);
      setPrs(prItems);
      setMemberJob(nextMemberJob);

      if (
        memberGenerationBaseline.current !== undefined &&
        nextMemberJob !== null &&
        nextMemberJob.status !== "pending" &&
        nextMemberJob.status !== "running"
      ) {
        const before = memberGenerationBaseline.current;
        memberGenerationBaseline.current = undefined;
        setMemberUnchanged(
          nextMemberJob.status === "succeeded" &&
            before !== null &&
            nextSummary?.generated_at === before,
        );
      }
      return true;
    } catch (error) {
      if (currentRequest !== requestId.current) return false;
      throw error;
    }
  }, [projectId, login]);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    setPollingStopped(false);
    let appliesToCurrentView = true;
    try {
      appliesToCurrentView = await fetchData();
    } catch (e) {
      setError(
        messageForError(e, { fallback: "貢献サマリーを取得できませんでした" }),
      );
    } finally {
      if (appliesToCurrentView) setLoading(false);
    }
  }, [enabled, fetchData]);

  useEffect(() => {
    load();
  }, [load]);

  const active =
    memberJob?.status === "pending" ||
    memberJob?.status === "running" ||
    prs.some(
      (item) =>
        item.job?.status === "pending" || item.job?.status === "running",
    );
  const pollingStartedAt = activeJobStartedAt([
    ...(memberJob ? [memberJob] : []),
    ...prs.flatMap((item) => (item.job ? [item.job] : [])),
  ]);

  const refreshGeneration = useCallback(async () => {
    try {
      // false は新しい取得世代が既に始まったという意味で、通信失敗ではない。
      await fetchData();
      return true;
    } catch {
      // 既存表示は保ったまま、共有ポーリング側で間隔を延ばして再試行する。
      return false;
    }
  }, [fetchData]);
  const stopPolling = useCallback((message: string) => {
    setError(message);
    setPollingStopped(true);
  }, []);
  useSummaryPolling({
    enabled: enabled && active && !loading && !pollingStopped,
    startedAt: pollingStartedAt,
    refresh: refreshGeneration,
    onStopped: stopPolling,
  });

  const generateMember = useCallback(async () => {
    requestId.current += 1;
    memberGenerationBaseline.current = summary?.generated_at ?? null;
    setMemberUnchanged(false);
    setStartingMember(true);
    setError(null);
    setPollingStopped(false);
    try {
      const job = await api.post<SummaryJob>(
        `/projects/${projectId}/summaries/${encodeURIComponent(login)}`,
      );
      setMemberJob(job);
    } catch (e) {
      memberGenerationBaseline.current = undefined;
      setError(
        messageForError(e, { fallback: "貢献サマリーの生成を開始できませんでした" }),
      );
    } finally {
      setStartingMember(false);
    }
  }, [projectId, login, summary?.generated_at]);

  const generatePr = useCallback(
    async (prNumber: number) => {
      requestId.current += 1;
      setStartingPrs((current) =>
        current.includes(prNumber) ? current : [...current, prNumber],
      );
      setError(null);
      setPollingStopped(false);
      try {
        const job = await api.post<SummaryJob>(
          `/projects/${projectId}/summaries/${encodeURIComponent(login)}/prs/${prNumber}`,
        );
        setPrs((current) =>
          current.map((item) =>
            item.pr_number === prNumber ? { ...item, job } : item,
          ),
        );
      } catch (e) {
        setError(
          messageForError(e, {
            codes: {
              SUMMARY_PR_NOT_FOUND:
                "このPRは同期済みの記録に見つかりませんでした。再読み込み後にお試しください。",
            },
            fallback: `PR #${prNumber} のサマリー生成を開始できませんでした`,
          }),
        );
      } finally {
        setStartingPrs((current) =>
          current.filter((number) => number !== prNumber),
        );
      }
    },
    [projectId, login],
  );

  return {
    summary,
    prs,
    memberJob,
    loading,
    error,
    startingMember,
    startingPrs,
    memberUnchanged,
    generateMember,
    generatePr,
    reload: load,
  };
}
