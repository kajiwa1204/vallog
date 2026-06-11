"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ScoreResponse } from "@/types";

export function useDashboard(projectId: string) {
  const [scores, setScores] = useState<ScoreResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchScores = useCallback(
    async (refresh: boolean) => {
      try {
        setError(null);
        const data = await api.get<ScoreResponse>(
          `/projects/${projectId}/scores${refresh ? "?refresh=true" : ""}`,
        );
        setScores(data);
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : "スコアの取得に失敗しました",
        );
      }
    },
    [projectId],
  );

  useEffect(() => {
    setLoading(true);
    fetchScores(false).finally(() => setLoading(false));
  }, [fetchScores]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await fetchScores(true);
    setRefreshing(false);
  }, [fetchScores]);

  return { scores, loading, refreshing, error, refresh };
}
