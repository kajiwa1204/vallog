"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { Member, Summary, SummaryJob } from "@/types";
import { activeJobStartedAt } from "./polling";
import { useSummaryPolling } from "./useSummaryPolling";

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
  const [generatingAll, setGeneratingAll] = useState(false);
  const [unchangedLogins, setUnchangedLogins] = useState<string[]>([]);
  const [pollingStopped, setPollingStopped] = useState(false);
  const requestId = useRef(0);
  const generationBaselines = useRef(new Map<string, string | null>());

  useEffect(() => {
    requestId.current += 1;
    generationBaselines.current.clear();
    setMembers([]);
    setSummaries([]);
    setJobs([]);
    setUnchangedLogins([]);
    setPollingStopped(false);
  }, [projectId]);

  const applyGenerationData = useCallback(
    (nextJobs: SummaryJob[], nextSummaries: Summary[]) => {
      setJobs(nextJobs);
      setSummaries(nextSummaries);
      setUnchangedLogins((current) => {
        const next = new Set(current);

        for (const job of nextJobs) {
          if (!generationBaselines.current.has(job.github_login)) continue;
          if (job.status === "pending" || job.status === "running") continue;

          const before = generationBaselines.current.get(job.github_login);
          generationBaselines.current.delete(job.github_login);
          const after = nextSummaries.find(
            (summary) => summary.github_login === job.github_login,
          )?.generated_at;
          if (job.status === "succeeded" && before !== null && after === before) {
            next.add(job.github_login);
          } else {
            next.delete(job.github_login);
          }
        }

        return [...next];
      });
    },
    [],
  );

  const load = useCallback(async () => {
    if (!enabled) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    setPollingStopped(false);
    try {
      const nextMembers = await api.get<Member[]>(`/projects/${projectId}/members`);
      const nextJobs = await api.get<SummaryJob[]>(
        `/projects/${projectId}/summary-jobs`,
      );
      const nextSummaries = await api.get<Summary[]>(
        `/projects/${projectId}/summaries`,
      );
      if (currentRequest !== requestId.current) return;
      setMembers(nextMembers);
      applyGenerationData(nextJobs, nextSummaries);
    } catch (e) {
      if (currentRequest !== requestId.current) return;
      setError(
        messageForError(e, {
          fallback: "貢献サマリーの情報を取得できませんでした",
        }),
      );
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  }, [projectId, enabled, applyGenerationData]);

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
  const pollingStartedAt = activeJobStartedAt(jobs);

  const refreshGeneration = useCallback(async () => {
    const currentRequest = ++requestId.current;
    try {
      // ジョブを先に読む。並列にすると summaries が完了commit直前、jobs が直後の
      // 順で返り、「完了だが結果なし」のままポーリングが止まりうる。
      const nextJobs = await api.get<SummaryJob[]>(
        `/projects/${projectId}/summary-jobs`,
      );
      const nextSummaries = await api.get<Summary[]>(
        `/projects/${projectId}/summaries`,
      );
      if (currentRequest !== requestId.current) return true;
      applyGenerationData(nextJobs, nextSummaries);
      return true;
    } catch {
      return false;
    }
  }, [projectId, applyGenerationData]);

  const stopPolling = useCallback((message: string) => {
    setError(message);
    setPollingStopped(true);
  }, []);
  useSummaryPolling({
    enabled: enabled && polling && !pollingStopped,
    startedAt: pollingStartedAt,
    refresh: refreshGeneration,
    onStopped: stopPolling,
  });

  const generate = useCallback(
    async (login: string) => {
      if (generatingAll) return false;
      requestId.current += 1;
      generationBaselines.current.set(
        login,
        summaries.find((summary) => summary.github_login === login)?.generated_at ??
          null,
      );
      setUnchangedLogins((current) => current.filter((item) => item !== login));
      setStartingLogins((current) =>
        current.includes(login) ? current : [...current, login],
      );
      setError(null);
      setPollingStopped(false);
      try {
        const job = await api.post<SummaryJob>(
          `/projects/${projectId}/summaries/${encodeURIComponent(login)}`,
        );
        setJobs((current) => replaceJob(current, job));
        return true;
      } catch (e) {
        generationBaselines.current.delete(login);
        setError(
          messageForError(e, { fallback: `${login} のサマリーを生成できませんでした` }),
        );
        return false;
      } finally {
        setStartingLogins((current) => current.filter((item) => item !== login));
      }
    },
    [projectId, generatingAll, summaries],
  );

  const generateAll = useCallback(async () => {
    if (generatingAll || startingLogins.length > 0) return;
    const targets = members.map((member) => member.github_login);
    if (targets.length === 0) return;
    requestId.current += 1;
    for (const login of targets) {
      generationBaselines.current.set(
        login,
        summaries.find((summary) => summary.github_login === login)?.generated_at ??
          null,
      );
    }
    setUnchangedLogins((current) =>
      current.filter((login) => !targets.includes(login)),
    );
    setGeneratingAll(true);
    setError(null);
    setPollingStopped(false);
    try {
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
      results.forEach((result, index) => {
        if (result.status === "rejected") {
          generationBaselines.current.delete(targets[index]);
        }
      });
      setJobs((current) =>
        succeeded.reduce((next, job) => replaceJob(next, job), current),
      );
      if (succeeded.length !== targets.length) {
        setError(
          "一部のメンバーの生成を開始できませんでした。個別に再試行できます。",
        );
      }
    } finally {
      setGeneratingAll(false);
    }
  }, [
    generatingAll,
    members,
    projectId,
    startingLogins.length,
    summaries,
  ]);

  return {
    members,
    summariesByLogin,
    jobsByLogin,
    loading,
    error,
    startingLogins,
    generatingAll,
    unchangedLogins,
    generate,
    generateAll,
    reload: load,
  };
}
