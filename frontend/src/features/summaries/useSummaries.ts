"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { Member, Summary, SummaryJob } from "@/types";

const POLL_INTERVAL_MS = 3000;

function replaceJob(jobs: SummaryJob[], next: SummaryJob): SummaryJob[] {
  return [next, ...jobs.filter((job) => job.github_login !== next.github_login)];
}

export function useSummaries(projectId: string, enabled = true) {
  const [members, setMembers] = useState<Member[]>([]);
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [jobs, setJobs] = useState<SummaryJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingLogins, setStartingLogins] = useState<string[]>([]);

  useEffect(() => {
    setMembers([]);
    setSummaries([]);
    setJobs([]);
  }, [projectId]);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const [nextMembers, nextSummaries, nextJobs] = await Promise.all([
        api.get<Member[]>(`/projects/${projectId}/members`),
        api.get<Summary[]>(`/projects/${projectId}/summaries`),
        api.get<SummaryJob[]>(`/projects/${projectId}/summary-jobs`),
      ]);
      setMembers(nextMembers);
      setSummaries(nextSummaries);
      setJobs(nextJobs);
    } catch (e) {
      setError(
        messageForError(e, {
          fallback: "貢献サマリーの情報を取得できませんでした",
        }),
      );
    } finally {
      setLoading(false);
    }
  }, [projectId, enabled]);

  useEffect(() => {
    load();
  }, [load]);

  const jobsByLogin = useMemo(
    () => new Map(jobs.map((job) => [job.github_login, job])),
    [jobs],
  );
  const summariesByLogin = useMemo(
    () => new Map(summaries.map((summary) => [summary.github_login, summary])),
    [summaries],
  );
  const polling = jobs.some(
    (job) => job.status === "pending" || job.status === "running",
  );

  const refreshGeneration = useCallback(async () => {
    try {
      // ジョブを先に読む。並列にすると summaries が完了commit直前、jobs が直後の
      // 順で返り、「完了だが結果なし」のままポーリングが止まりうる。
      const nextJobs = await api.get<SummaryJob[]>(
        `/projects/${projectId}/summary-jobs`,
      );
      const nextSummaries = await api.get<Summary[]>(
        `/projects/${projectId}/summaries`,
      );
      setJobs(nextJobs);
      setSummaries(nextSummaries);
    } catch {
      // 一時的なポーリング失敗で生成状態をエラーに倒さない。次回で再試行する。
    }
  }, [projectId]);

  useEffect(() => {
    if (!enabled || !polling) return;
    const timer = window.setInterval(refreshGeneration, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [enabled, polling, refreshGeneration]);

  const generate = useCallback(
    async (login: string) => {
      setStartingLogins((current) =>
        current.includes(login) ? current : [...current, login],
      );
      setError(null);
      try {
        const job = await api.post<SummaryJob>(
          `/projects/${projectId}/summaries/${encodeURIComponent(login)}`,
        );
        setJobs((current) => replaceJob(current, job));
        return true;
      } catch (e) {
        setError(
          messageForError(e, { fallback: `${login} のサマリーを生成できませんでした` }),
        );
        return false;
      } finally {
        setStartingLogins((current) => current.filter((item) => item !== login));
      }
    },
    [projectId],
  );

  const generateAll = useCallback(async () => {
    const targets = members.map((member) => member.github_login);
    if (targets.length === 0) return;
    setStartingLogins(targets);
    setError(null);
    const results = await Promise.allSettled(
      targets.map((login) =>
        api.post<SummaryJob>(
          `/projects/${projectId}/summaries/${encodeURIComponent(login)}`,
        ),
      ),
    );
    const succeeded = results.flatMap((result) =>
      result.status === "fulfilled" ? [result.value] : [],
    );
    setJobs((current) =>
      succeeded.reduce((next, job) => replaceJob(next, job), current),
    );
    setStartingLogins([]);
    if (succeeded.length !== targets.length) {
      setError("一部のメンバーの生成を開始できませんでした。個別に再試行できます。");
    }
  }, [members, projectId]);

  return {
    members,
    summariesByLogin,
    jobsByLogin,
    loading,
    error,
    startingLogins,
    generate,
    generateAll,
    reload: load,
  };
}
