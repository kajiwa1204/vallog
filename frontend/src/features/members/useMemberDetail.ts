"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { MemberDetail, Summary } from "@/types";

export function useMemberDetail(projectId: string, login: string) {
  const [detail, setDetail] = useState<MemberDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    };
  }, [projectId, login]);

  const [generating, setGenerating] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const generateSummary = useCallback(async () => {
    setGenerating(true);
    setSummaryError(null);
    try {
      const summary = await api.post<Summary>(
        `/projects/${projectId}/summaries/${login}`,
      );
      setDetail((prev) => (prev ? { ...prev, summary } : prev));
    } catch (e) {
      setSummaryError(
        e instanceof ApiError ? e.message : "サマリーの生成に失敗しました",
      );
    } finally {
      setGenerating(false);
    }
  }, [projectId, login]);

  return { detail, loading, error, generating, summaryError, generateSummary };
}
