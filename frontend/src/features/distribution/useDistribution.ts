"use client";

import { useMemo, useState } from "react";
import { computeDistribution, defaultWeights, mockScores } from "@/lib/mockData";
import type { DistributionItem, Weight } from "@/types";

export type ManualOverride = {
  amount: number;
  reason: string;
  editedBy: string;
  editedByAvatar: string;
  editedAt: string;
};

export type EditLog = {
  id: string;
  login: string;
  name: string;
  from: number;
  to: number;
  reason: string;
  editedBy: string;
  editedByAvatar: string;
  editedAt: string;
};

export type SavedProposal = {
  id: string;
  name: string;
  totalReward: number;
  weights: Weight;
  overrides: Record<string, ManualOverride>;
};

const initialProposals: SavedProposal[] = [
  {
    id: "balanced",
    name: "案A: バランス重視（初期値）",
    totalReward: 300000,
    weights: { issue: 1.0, pr: 2.0, review: 1.5, tat: 1.0, sp: 1.0 },
    overrides: {},
  },
];

const applyOverrides = (
  base: DistributionItem[],
  overrides: Record<string, ManualOverride>,
  totalReward: number,
): DistributionItem[] => {
  const adjusted = base.map((item) =>
    overrides[item.login]
      ? { ...item, manualOverride: overrides[item.login].amount }
      : { ...item },
  );
  const sum = adjusted.reduce((acc, item) => acc + (item.manualOverride ?? item.amount), 0);
  return adjusted.map((item) => ({
    ...item,
    ratio: totalReward > 0 ? (item.manualOverride ?? item.amount) / sum : 0,
  }));
};

const currentUser = { login: "shou6439", name: "Kameda Masato", avatar: "https://avatars.githubusercontent.com/u/82638006?v=4" };

export function useDistribution() {
  const [totalReward, setTotalReward] = useState(300000);
  const [weights, setWeights] = useState<Weight>(defaultWeights);
  const [overrides, setOverrides] = useState<Record<string, ManualOverride>>({});
  const [editLog, setEditLog] = useState<EditLog[]>([]);
  const [proposals, setProposals] = useState<SavedProposal[]>(initialProposals);

  const baseline = useMemo(
    () => computeDistribution(totalReward, weights, mockScores),
    [totalReward, weights],
  );

  const preview = useMemo(
    () => ({
      ...baseline,
      items: applyOverrides(baseline.items, overrides, totalReward),
    }),
    [baseline, overrides, totalReward],
  );

  const savedPreviews = useMemo(
    () =>
      proposals.map((p) => {
        const base = computeDistribution(p.totalReward, p.weights, mockScores);
        return { ...base, items: applyOverrides(base.items, p.overrides, p.totalReward) };
      }),
    [proposals],
  );

  const applyOverride = (login: string, name: string, amount: number, reason: string) => {
    const baseItem = baseline.items.find((i) => i.login === login);
    if (!baseItem) return;
    const fromAmount = overrides[login]?.amount ?? baseItem.amount;
    setOverrides((prev) => ({
      ...prev,
      [login]: {
        amount,
        reason,
        editedBy: currentUser.name,
        editedByAvatar: currentUser.avatar,
        editedAt: new Date().toISOString(),
      },
    }));
    setEditLog((prev) => [
      {
        id: `edit-${prev.length + 1}-${Date.now()}`,
        login,
        name,
        from: fromAmount,
        to: amount,
        reason,
        editedBy: currentUser.name,
        editedByAvatar: currentUser.avatar,
        editedAt: new Date().toISOString(),
      },
      ...prev,
    ]);
  };

  const clearOverride = (login: string) => {
    setOverrides((prev) => {
      const next = { ...prev };
      delete next[login];
      return next;
    });
  };

  const resetAllOverrides = () => {
    setOverrides({});
  };

  const saveProposal = (name: string) => {
    setProposals((prev) => [
      ...prev,
      {
        id: `proposal-${prev.length + 1}`,
        name,
        totalReward,
        weights,
        overrides,
      },
    ]);
  };

  const loadProposal = (id: string) => {
    const target = proposals.find((p) => p.id === id);
    if (!target) return;
    setTotalReward(target.totalReward);
    setWeights(target.weights);
    setOverrides(target.overrides);
  };

  return {
    totalReward,
    setTotalReward,
    weights,
    setWeights,
    preview,
    overrides,
    applyOverride,
    clearOverride,
    resetAllOverrides,
    editLog,
    proposals,
    savedPreviews,
    saveProposal,
    loadProposal,
  };
}
