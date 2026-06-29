"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { ProjectListItem } from "@/types";

type State = {
  projects: ProjectListItem[];
  loading: boolean;
  error: string | null;
};

export function useProjects() {
  const [state, setState] = useState<State>({
    projects: [],
    loading: true,
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const projects = await api.get<ProjectListItem[]>("/projects");
      setState({ projects, loading: false, error: null });
    } catch (e) {
      const message = messageForError(e, {
        fallback: "プロジェクトの取得に失敗しました",
      });
      setState({ projects: [], loading: false, error: message });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}
