"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { MemberDetail, SummaryJob } from "@/types";

const POLL_INTERVAL_MS = 3000;

export function useMemberDetail(projectId: string, login: string) {
  const [detail, setDetail] = useState<MemberDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [generating, setGenerating] = useState(false);
  const [jobProgress, setJobProgress] = useState<{
    done: number;
    total: number;
  } | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const reloadDetail = useCallback(async () => {
    const data = await api.get<MemberDetail>(
      `/projects/${projectId}/members/${login}`,
    );
    setDetail(data);
  }, [projectId, login]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<MemberDetail>(`/projects/${projectId}/members/${login}`)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e) => {
        if (!cancelled)
          setError(
            e instanceof ApiError ? e.message : "読み込みに失敗しました",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [projectId, login, stopPolling]);

  const pollJob = useCallback(() => {
    stopPolling();
    intervalRef.current = setInterval(async () => {
      try {
        const jobs = await api.get<SummaryJob[]>(
          `/projects/${projectId}/summary-jobs`,
        );
        const job = jobs.find((j) => j.github_login === login);

        if (!job) {
          stopPolling();
          setGenerating(false);
          return;
        }

        if (job.status === "running" || job.status === "pending") {
          setJobProgress({ done: job.done_prs, total: job.total_prs });
          return;
        }

        // 完了 or 失敗でポーリング停止
        stopPolling();
        setGenerating(false);
        setJobProgress(null);

        if (job.status === "succeeded") {
          await reloadDetail();
        } else if (job.status === "failed") {
          setSummaryError(job.error ?? "サマリーの生成に失敗しました");
        }
      } catch (e) {
        stopPolling();
        setGenerating(false);
        setJobProgress(null);
        setSummaryError(
          e instanceof ApiError ? e.message : "ジョブの取得に失敗しました",
        );
      }
    }, POLL_INTERVAL_MS);
  }, [projectId, login, stopPolling, reloadDetail]);

  const generateSummary = useCallback(async () => {
    setGenerating(true);
    setSummaryError(null);
    setJobProgress(null);
    try {
      await api.post<SummaryJob>(`/projects/${projectId}/summaries/${login}`);
      pollJob();
    } catch (e) {
      setGenerating(false);
      setSummaryError(
        e instanceof ApiError ? e.message : "サマリーの生成に失敗しました",
      );
    }
  }, [projectId, login, pollJob]);

  return {
    detail,
    loading,
    error,
    generating,
    jobProgress,
    summaryError,
    generateSummary,
  };
}
