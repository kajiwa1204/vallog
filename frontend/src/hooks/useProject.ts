"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Project } from "@/types";

// プロジェクト共通情報（名前・重み・リポジトリ）。各画面のAppShell表示に使う
export function useProject(projectId: string) {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setProject(await api.get<Project>(`/projects/${projectId}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "読み込みに失敗しました");
    }
  }, [projectId]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { project, error, reload, setProject };
}
