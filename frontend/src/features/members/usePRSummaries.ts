"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { PRSummaryItem } from "@/types";

const POLL_INTERVAL_MS = 3000;

function hasActiveJob(item: PRSummaryItem): boolean {
  return (
    item.job?.status === "pending" || item.job?.status === "running"
  );
}

export function usePRSummaries(projectId: string, login: string) {
  const [items, setItems] = useState<PRSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // pr_number → ポーリング中フラグ
  const pollingRef = useRef<Map<number, ReturnType<typeof setInterval>>>(new Map());

  const fetchItems = useCallback(async (): Promise<PRSummaryItem[]> => {
    const data = await api.get<PRSummaryItem[]>(
      `/projects/${projectId}/summaries/${login}/prs`,
    );
    setItems(data);
    return data;
  }, [projectId, login]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<PRSummaryItem[]>(`/projects/${projectId}/summaries/${login}/prs`)
      .then((data) => {
        if (cancelled) return;
        setItems(data);
        // 初期ロード時点でアクティブなジョブがあればポーリング開始
        data.forEach((item) => {
          if (hasActiveJob(item)) startPollingPr(item.pr_number);
        });
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof ApiError ? e.message : "PR一覧の取得に失敗しました");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      stopAllPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, login]);

  const stopPollingPr = useCallback((prNumber: number) => {
    const timer = pollingRef.current.get(prNumber);
    if (timer !== undefined) {
      clearInterval(timer);
      pollingRef.current.delete(prNumber);
    }
  }, []);

  const stopAllPolling = useCallback(() => {
    pollingRef.current.forEach((timer) => clearInterval(timer));
    pollingRef.current.clear();
  }, []);

  const startPollingPr = useCallback(
    (prNumber: number) => {
      // 二重起動を防ぐ
      if (pollingRef.current.has(prNumber)) return;

      const timer = setInterval(async () => {
        try {
          const data = await fetchItems();
          const item = data.find((i) => i.pr_number === prNumber);
          if (!item || !hasActiveJob(item)) {
            stopPollingPr(prNumber);
          }
        } catch {
          stopPollingPr(prNumber);
        }
      }, POLL_INTERVAL_MS);

      pollingRef.current.set(prNumber, timer);
    },
    [fetchItems, stopPollingPr],
  );

  const generatePrSummary = useCallback(
    async (prNumber: number) => {
      await api.post(
        `/projects/${projectId}/summaries/${login}/prs/${prNumber}`,
      );
      // POST後に一覧を再取得してジョブ状態を反映
      const data = await fetchItems();
      const item = data.find((i) => i.pr_number === prNumber);
      if (item && hasActiveJob(item)) {
        startPollingPr(prNumber);
      }
    },
    [projectId, login, fetchItems, startPollingPr],
  );

  return { items, loading, error, generatePrSummary };
}
