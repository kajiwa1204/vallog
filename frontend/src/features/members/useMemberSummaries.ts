"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { PRSummaryItem, Summary, SummaryJob } from "@/types";

const POLL_INTERVAL_MS = 3000;

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

  useEffect(() => {
    // 動的ルート間の遷移ではコンポーネントが再利用される。前の人の要約を一瞬でも
    // 次の人のものとして出さないよう、識別子が変わった時点で表示データを空にする。
    setSummary(null);
    setPrs([]);
    setMemberJob(null);
  }, [projectId, login]);

  const fetchData = useCallback(async () => {
    // メンバー一括ジョブの完了を先に観測してから結果を読む。並列だと summaries だけ
    // 完了commit前の値になり、ジョブ完了によってポーリングが止まる競合がある。
    const jobs = await api.get<SummaryJob[]>(
      `/projects/${projectId}/summary-jobs`,
    );
    const [summaries, prItems] = await Promise.all([
      api.get<Summary[]>(`/projects/${projectId}/summaries`),
      api.get<PRSummaryItem[]>(
        `/projects/${projectId}/summaries/${encodeURIComponent(login)}/prs`,
      ),
    ]);
    setSummary(
      summaries.find((item) => item.github_login === login) ?? null,
    );
    setPrs(prItems);
    setMemberJob(jobs.find((job) => job.github_login === login) ?? null);
  }, [projectId, login]);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      await fetchData();
    } catch (e) {
      setError(
        messageForError(e, { fallback: "貢献サマリーを取得できませんでした" }),
      );
    } finally {
      setLoading(false);
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

  useEffect(() => {
    if (!enabled || !active) return;
    const timer = window.setInterval(() => {
      fetchData().catch(() => {
        // 一時的な失敗は次のポーリングで回復させる。既存表示は消さない。
      });
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [enabled, active, fetchData]);

  const generateMember = useCallback(async () => {
    setStartingMember(true);
    setError(null);
    try {
      const job = await api.post<SummaryJob>(
        `/projects/${projectId}/summaries/${encodeURIComponent(login)}`,
      );
      setMemberJob(job);
    } catch (e) {
      setError(
        messageForError(e, { fallback: "貢献サマリーの生成を開始できませんでした" }),
      );
    } finally {
      setStartingMember(false);
    }
  }, [projectId, login]);

  const generatePr = useCallback(
    async (prNumber: number) => {
      setStartingPrs((current) =>
        current.includes(prNumber) ? current : [...current, prNumber],
      );
      setError(null);
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
    generateMember,
    generatePr,
    reload: load,
  };
}
