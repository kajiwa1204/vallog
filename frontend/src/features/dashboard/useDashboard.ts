"use client";

import { useCallback, useEffect, useState } from "react";
import { useChangeLog } from "@/hooks/useChangeLog";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { DashboardResponse } from "@/types";

// バックエンドの既定値と揃える（backend/app/services/dashboard.py の DEFAULT_PULSE_DAYS）
const PULSE_DAYS = 14;

const LAST_SEEN_KEY = (projectId: string) => `vallog:lastSeen:${projectId}`;

/**
 * 前回このダッシュボードを見た時刻を読み、いまの時刻で上書きする。
 *
 * サーバに持たせないのは、「前回いつ見たか」が本質的にクライアントの状態で、
 * 新規テーブルを足すほどの情報ではないため。端末をまたげないのは承知の上で、
 * 「毎日開く理由」を作る最小の一手として置く。必要になったらサーバへ移せる。
 */
function readAndBumpLastSeen(projectId: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    const key = LAST_SEEN_KEY(projectId);
    const previous = window.localStorage.getItem(key);
    window.localStorage.setItem(key, new Date().toISOString());
    return previous;
  } catch {
    // プライベートモード等で localStorage が使えない場合は印を出さないだけにする
    return null;
  }
}

/**
 * ダッシュボード（画面4）のデータ取得。
 *
 * 変化ログ（主役）とチーム状況パネル4種を別々に取る。1本にまとめないのは、変化ログが
 * #13/#14/#18 で共有される取得フックで、ここだけの都合で形を変えられないため。
 * どちらも ensure_synced を通るが、同期中なら待たずに今のキャッシュを返す実装なので
 * 二重同期にはならない。
 *
 * スコア（GET /scores）は呼ばない。ダッシュボードにスコアは載せない方針
 * （docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
 */
export function useDashboard(projectId: string, enabled = true) {
  const [selectedMember, setSelectedMember] = useState<string | null>(null);
  const changelog = useChangeLog(projectId, {
    member: selectedMember ?? undefined,
    enabled,
  });

  // 絞り込みチップに出す顔ぶれ。絞り込み中は変化ログが1人分に減るので、そこから毎回
  // 作り直すとチップ自体が1個に潰れて他の人に切り替えられなくなる。全員表示のときだけ更新する。
  // 並びは辞書順。取得順（時系列）のままだと「直近に動いた人」が先頭に来て、
  // ダッシュボードが出さないはずの序列を暗に作ってしまう
  const [roster, setRoster] = useState<string[]>([]);

  const [panels, setPanels] = useState<DashboardResponse | null>(null);
  const [panelsError, setPanelsError] = useState<string | null>(null);
  const [panelsLoading, setPanelsLoading] = useState(true);

  // 初回マウント時に1度だけ読む。再読み込みのたびに更新すると、押した瞬間に
  // 新着が全部消える
  const [newSince, setNewSince] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    setNewSince(readAndBumpLastSeen(projectId));
  }, [projectId, enabled]);

  const loadPanels = useCallback(async () => {
    if (!enabled) return;
    setPanelsLoading(true);
    setPanelsError(null);
    try {
      const params = new URLSearchParams({
        days: String(PULSE_DAYS),
        // getTimezoneOffset() は「UTCからどれだけ遅れているか」を返すので符号を反転する。
        // これを渡さないと日次バケットの境界が 09:00 JST になり、朝まで「今日」が空になる
        tz_offset_minutes: String(-new Date().getTimezoneOffset()),
      });
      setPanels(
        await api.get<DashboardResponse>(
          `/projects/${projectId}/dashboard?${params}`,
        ),
      );
    } catch (e) {
      setPanelsError(
        messageForError(e, {
          // GitHubがprivateリポジトリを404で返すため、権限不足がそのまま
          // 「見つかりません」に見える。原因を切り分けられる文言にする
          codes: {
            REPO_NOT_FOUND:
              "GitHubリポジトリを読み取れませんでした。リポジトリへのアクセス権限を確認してください。",
          },
          fallback: "チームの状況を取得できませんでした",
        }),
      );
    } finally {
      setPanelsLoading(false);
    }
  }, [projectId, enabled]);

  useEffect(() => {
    loadPanels();
  }, [loadPanels]);

  const entries = changelog.entries;
  useEffect(() => {
    if (selectedMember !== null) return;
    setRoster(
      Array.from(new Set(entries.map((e) => e.actor_login))).sort((a, b) =>
        a.localeCompare(b),
      ),
    );
  }, [entries, selectedMember]);

  const reload = useCallback(() => {
    loadPanels();
    changelog.reload();
  }, [loadPanels, changelog]);

  // 初回同期がまだ終わっていない。「データが無い」と区別してローディングを出すために使う
  const syncing = panels !== null && panels.synced_at === null;

  return {
    panels,
    panelsError,
    panelsLoading,
    changelog,
    newSince,
    roster,
    selectedMember,
    selectMember: setSelectedMember,
    syncing,
    reload,
  };
}
