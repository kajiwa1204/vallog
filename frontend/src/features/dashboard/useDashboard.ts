"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useChangeLog } from "@/hooks/useChangeLog";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { DashboardResponse } from "@/types";

// バックエンドの既定値と揃える（backend/app/services/dashboard.py の DEFAULT_PULSE_DAYS）
const PULSE_DAYS = 14;

const LAST_SEEN_KEY = (projectId: string) => `vallog:lastSeen:${projectId}`;

/**
 * この「訪問」で確定した新着基準（projectId → newSince）。
 *
 * **モジュール変数なのが要点。** 保持したい寿命が「1回の訪問」だから。
 *
 * - フック内の ref だと、ページ遷移でアンマウントされた時点で失われる。
 *   ダッシュボード⇄メンバー詳細の往復（#14 で主要動線になった）で戻るたびに
 *   基準が「今」に更新され、新着の印が全部消えていた
 * - かといって sessionStorage に置くと、今度は**リロードしても生き残る**ので
 *   何度読み直しても印が消えなくなる（振り切りすぎ）
 *
 * モジュール変数は SPA 内の遷移では生き、ページの再読み込みと別タブでは消える。
 * これがちょうど「1回の訪問」の粒度になる。
 */
const settledNewSince = new Map<string, string | null>();

/**
 * 前回このダッシュボードを見た時刻を読み、いまの時刻で上書きする。
 *
 * サーバに持たせないのは、「前回いつ見たか」が本質的にクライアントの状態で、
 * 新規テーブルを足すほどの情報ではないため。端末をまたげないのは承知の上で、
 * 「毎日開く理由」を作る最小の一手として置く。必要になったらサーバへ移せる。
 */
function readAndBumpLastSeen(projectId: string): string | null {
  if (typeof window === "undefined") return null;

  // この訪問で確定済みなら、その基準を返すだけにして上書きしない。
  // 上書きすると往復のたびに基準が「今」になり、新着の印が消える
  if (settledNewSince.has(projectId)) {
    return settledNewSince.get(projectId) ?? null;
  }

  try {
    const key = LAST_SEEN_KEY(projectId);
    const previous = window.localStorage.getItem(key);
    window.localStorage.setItem(key, new Date().toISOString());
    settledNewSince.set(projectId, previous);
    return previous;
  } catch {
    // プライベートモード等でストレージが使えない場合は印を出さないだけにする。
    // 確定済みとして記録し、遷移のたびに例外を踏み直さない
    settledNewSince.set(projectId, null);
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

  // パネルの取得が済むまで変化ログを止める。両方が ensure_synced を通るため、
  // 並列に投げると TTL 切れの回に「ロックを取れた側は新しいキャッシュ、取れなかった
  // 側は古いキャッシュ」という別世代の同居が起きる。活動リズムのバーが今日3件と
  // 言っているのに一覧に今日の行が無い、という読めない画面がこれ。
  // GitHubがエラーを返す回も、どちらの領域がエラー表示になるかがレースで決まって
  // 再現しなくなる。
  // 直列にしても待ち時間はほとんど増えない。2本目は1本目が温めたキャッシュを引くため。
  const [panelsSettled, setPanelsSettled] = useState(false);
  const changelog = useChangeLog(projectId, {
    member: selectedMember ?? undefined,
    enabled: enabled && panelsSettled,
  });

  const [panels, setPanels] = useState<DashboardResponse | null>(null);
  const [panelsError, setPanelsError] = useState<string | null>(null);
  const [panelsLoading, setPanelsLoading] = useState(true);

  // 初回に1度だけ読む。再読み込みのたびに更新すると、押した瞬間に新着が全部消える。
  //
  // bump は「変化ログの取得に成功した回」に限る。取得の成否と無関係に走らせると、
  // エラー画面を1度見ただけで、それまで溜まっていた新着の印が永久に消える。
  //
  // ref で番をするのは、この関数が「読んでから同じキーを上書きする」ため冪等でなく、
  // 2回走ると2回目が「たった今書いた値」を読んで新着が0件になるから。いまは
  // useAuth が非同期で enabled が mount 時に false のため StrictMode の二重実行を
  // 免れているが、認証がContext化なりで同期的に解決するようになった瞬間に壊れる。
  // しかも開発時にしか出ず、「前回から何も起きていない」と見分けが付かない
  const [newSince, setNewSince] = useState<string | null>(null);
  const bumpedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled || changelog.loading || changelog.error !== null) return;
    if (bumpedFor.current === projectId) return;
    bumpedFor.current = projectId;
    setNewSince(readAndBumpLastSeen(projectId));
  }, [projectId, enabled, changelog.loading, changelog.error]);

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
      // 失敗しても立てる。同期を試みた事実は同じなので、変化ログは後続で
      // 同じ結果（成功なら温まったキャッシュ、失敗なら同じエラー）を受ける
      setPanelsSettled(true);
    }
  }, [projectId, enabled]);

  useEffect(() => {
    loadPanels();
  }, [loadPanels]);

  // 絞り込みチップに出す顔ぶれ。サーバが返す（#109）。
  //
  // 読み込み済みのエントリから作っていたが、それだと取得件数に顔ぶれが依存する。
  // 既定の50件では直近に動いていない人がチップから消え、その人の記録に辿り着けなく
  // なっていた。絞り込み中はエントリが1人分に減るため「全員表示のときだけ更新する」
  // という回避も要り、状態が増えていた。サーバはキャッシュ全件を見るのでどちらも要らない。
  // Issueの担当しかしていない人（actor_login に現れない）も拾える。
  const roster = panels?.roster ?? [];

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
