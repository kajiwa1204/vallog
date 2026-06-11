"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type {
  CategoryWeights,
  EditLog,
  Proposal,
  ProposalListItem,
  Summary,
} from "@/types";

export function useDistribution(projectId: string) {
  const [proposals, setProposals] = useState<ProposalListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [logs, setLogs] = useState<EditLog[]>([]);
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    const list = await api.get<ProposalListItem[]>(
      `/projects/${projectId}/distributions`,
    );
    setProposals(list);
    return list;
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [list, sums] = await Promise.all([
          api.get<ProposalListItem[]>(`/projects/${projectId}/distributions`),
          api.get<Summary[]>(`/projects/${projectId}/summaries`),
        ]);
        if (cancelled) return;
        setProposals(list);
        setSummaries(sums);
        if (list.length > 0) setSelectedId(list[0].id);
      } catch (e) {
        if (!cancelled)
          setError(
            e instanceof ApiError ? e.message : "読み込みに失敗しました",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (!selectedId) {
      setProposal(null);
      setLogs([]);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    Promise.all([
      api.get<Proposal>(`/projects/${projectId}/distributions/${selectedId}`),
      api.get<EditLog[]>(
        `/projects/${projectId}/distributions/${selectedId}/logs`,
      ),
    ])
      .then(([p, l]) => {
        if (cancelled) return;
        setProposal(p);
        setLogs(l);
      })
      .catch((e) => {
        if (!cancelled)
          setError(
            e instanceof ApiError ? e.message : "読み込みに失敗しました",
          );
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, selectedId]);

  const refreshDetail = useCallback(
    async (updated: Proposal) => {
      setProposal(updated);
      setLogs(
        await api.get<EditLog[]>(
          `/projects/${projectId}/distributions/${updated.id}/logs`,
        ),
      );
      await loadList();
    },
    [projectId, loadList],
  );

  const createProposal = useCallback(
    async (title: string, totalAmount: string | null) => {
      const created = await api.post<Proposal>(
        `/projects/${projectId}/distributions`,
        {
          title,
          total_amount: totalAmount || null,
        },
      );
      await loadList();
      setSelectedId(created.id);
      return created;
    },
    [projectId, loadList],
  );

  const update = useCallback(
    async (
      payload: {
        reason: string;
        title?: string;
        total_amount?: string;
        weights?: CategoryWeights;
        items?: { github_login: string; ratio: string }[];
      },
    ) => {
      if (!selectedId) return;
      const updated = await api.patch<Proposal>(
        `/projects/${projectId}/distributions/${selectedId}`,
        payload,
      );
      await refreshDetail(updated);
    },
    [projectId, selectedId, refreshDetail],
  );

  const agree = useCallback(async () => {
    if (!selectedId) return;
    const updated = await api.post<Proposal>(
      `/projects/${projectId}/distributions/${selectedId}/agree`,
    );
    await refreshDetail(updated);
  }, [projectId, selectedId, refreshDetail]);

  return {
    proposals,
    selectedId,
    setSelectedId,
    proposal,
    logs,
    summaries,
    loading,
    detailLoading,
    error,
    createProposal,
    update,
    agree,
  };
}
