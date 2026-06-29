"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { Project } from "@/types";

// プロジェクト共通情報（名前・重み・リポジトリ）。各画面のAppShell表示に使う
export function useProject(projectId: string) {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProject(await api.get<Project>(`/projects/${projectId}`));
    } catch (e) {
      setError(
        messageForError(e, {
          404: "プロジェクトが見つかりません",
          fallback: "プロジェクトの読み込みに失敗しました",
        }),
      );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { project, error, loading, reload, setProject };
}
