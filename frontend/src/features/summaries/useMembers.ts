"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Member } from "@/types";

export function useMembers(projectId: string) {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<Member[]>(`/projects/${projectId}/members`)
      .then((data) => {
        if (!cancelled) setMembers(data);
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof ApiError ? e.message : "メンバーの取得に失敗しました");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return { members, loading, error };
}
