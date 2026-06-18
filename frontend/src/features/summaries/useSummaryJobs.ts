"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Summary, SummaryJob } from "@/types";

const POLL_INTERVAL_MS = 3000;

function hasActiveJobs(jobs: SummaryJob[]): boolean {
  return jobs.some((j) => j.status === "pending" || j.status === "running");
}

export function useSummaryJobs(projectId: string, logins: string[]) {
  const [jobs, setJobs] = useState<SummaryJob[]>([]);
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const fetchSummaries = useCallback(async () => {
    try {
      const data = await api.get<Summary[]>(`/projects/${projectId}/summaries`);
      setSummaries(data);
    } catch {
      // サマリー取得失敗はポーリング継続を妨げない
    }
  }, [projectId]);

  const fetchJobs = useCallback(async (): Promise<SummaryJob[]> => {
    const data = await api.get<SummaryJob[]>(
      `/projects/${projectId}/summary-jobs`,
    );
    setJobs(data);
    return data;
  }, [projectId]);

  // アクティブなジョブが完了に変わったタイミングでサマリーを再取得する
  const fetchJobsAndUpdateSummaries = useCallback(
    async (prevJobs: SummaryJob[]) => {
      try {
        const next = await fetchJobs();
        const justFinished = next.filter(
          (j) =>
            j.status === "succeeded" &&
            prevJobs.some(
              (p) =>
                p.github_login === j.github_login &&
                (p.status === "pending" || p.status === "running"),
            ),
        );
        if (justFinished.length > 0) {
          await fetchSummaries();
        }
        if (!hasActiveJobs(next)) {
          stopPolling();
        }
        return next;
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "ジョブの取得に失敗しました");
        stopPolling();
        return [] as SummaryJob[];
      }
    },
    [fetchJobs, fetchSummaries, stopPolling],
  );

  const startPolling = useCallback(
    (currentJobs: SummaryJob[]) => {
      stopPolling();
      let prev = currentJobs;
      intervalRef.current = setInterval(async () => {
        prev = await fetchJobsAndUpdateSummaries(prev);
      }, POLL_INTERVAL_MS);
    },
    [fetchJobsAndUpdateSummaries, stopPolling],
  );

  // 初期ロード
  useEffect(() => {
    if (logins.length === 0) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([
      api.get<SummaryJob[]>(`/projects/${projectId}/summary-jobs`),
      api.get<Summary[]>(`/projects/${projectId}/summaries`),
    ])
      .then(([jobsData, summariesData]) => {
        if (cancelled) return;
        setJobs(jobsData);
        setSummaries(summariesData);
        if (hasActiveJobs(jobsData)) {
          startPolling(jobsData);
        }
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof ApiError ? e.message : "読み込みに失敗しました");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [projectId, logins.length, startPolling, stopPolling]);

  const generateOne = useCallback(
    async (login: string) => {
      await api.post<SummaryJob>(`/projects/${projectId}/summaries/${login}`);
      const next = await fetchJobs();
      if (hasActiveJobs(next)) {
        startPolling(next);
      }
    },
    [projectId, fetchJobs, startPolling],
  );

  // 全員分を直列でPOSTしてからポーリング開始
  const generateAll = useCallback(async () => {
    for (const login of logins) {
      try {
        await api.post<SummaryJob>(`/projects/${projectId}/summaries/${login}`);
      } catch {
        // 個別失敗でも他のメンバー分は続行する
      }
    }
    const next = await fetchJobs();
    if (hasActiveJobs(next)) {
      startPolling(next);
    }
  }, [projectId, logins, fetchJobs, startPolling]);

  return {
    jobs,
    summaries,
    loading,
    error,
    generateOne,
    generateAll,
  };
}
