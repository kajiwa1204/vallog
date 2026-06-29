"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { Project } from "@/types";

// プロジェクト共通情報（名前・重み・リポジトリ）。各画面のAppShell表示に使う
// enabled=false の間は取得を保留する（認証確定前の無駄な 401 往復を避ける）
export function useProject(projectId: string, enabled = true) {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!enabled) return;
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
  }, [projectId, enabled]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { project, error, loading, reload, setProject };
}
