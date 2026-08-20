"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { ChangeLogEntry, ChangeLogResponse } from "@/types";

// バックエンドの既定値と揃える（backend/app/services/changelog.py の DEFAULT_LIMIT）
const PAGE_SIZE = 50;

/**
 * 1リクエストで取れる上限。**バックエンドの受理範囲と揃えること**
 * （backend/app/routers/changelog.py の `Query(ge=1, le=200)`）。
 *
 * 超えると 422 になるだけでは済まない。limit は state に残るので、その後の再試行も
 * 再読み込みも同じ値を投げ直し、ページを丸ごと読み直すまで復帰できなくなる。
 * さらに 422 は FastAPI のバリデーションエラーで detail が配列のため、api.ts は
 * code を取り出せず、画面には原因を語れない既定文言しか出せない。
 *
 * 「押せない」を制御フローで保証する（loadMore で丸め、hasMore を上限で閉じる）。
 */
const MAX_LIMIT = 200;

type Options = {
  // 未指定ならチーム全体。指定するとそのメンバーの変化だけに絞る（画面5・7）
  member?: string;
  // enabled=false の間は取得を保留する（認証確定前の無駄な 401 往復を避ける）
  enabled?: boolean;
  // 1回に取る件数。画面5は表示中の行から件数や活動量を数えるため、既定より深く
  // 取らないと集計が打ち切りに引きずられる。「もっと見る」の刻みも同じ値になる。
  // MAX_LIMIT を超える値を渡しても丸められる
  pageSize?: number;
};

/**
 * 押しても状況を悪くするだけのエラー。
 *
 * 再試行は ensure_synced を通ってまたGitHubを叩くので、利用上限に当たっている間は
 * 押させてはいけない。呼び出し側はこれが false のとき再試行導線を出さない。
 */
const NOT_RETRYABLE: string[] = ["GITHUB_RATE_LIMITED", "GITHUB_FORBIDDEN"];

export function isRetryableChangeLogError(code: string | null): boolean {
  return code === null || !NOT_RETRYABLE.includes(code);
}

/**
 * 変化ログの取得（#77）。ダッシュボード・メンバー詳細・分配で共有する。
 *
 * ページングは limit を増やして取り直す方式にしている。カーソル方式にしないのは、
 * 3テーブルを時系列マージするため「続きの位置」を単一のキーで表せないため。
 * 取得元はキャッシュ済みデータで件数も上限で頭打ちなので、再取得のコストは小さい。
 */
export function useChangeLog(
  projectId: string,
  { member, enabled = true, pageSize = PAGE_SIZE }: Options = {},
) {
  const size = Math.min(pageSize, MAX_LIMIT);

  const [entries, setEntries] = useState<ChangeLogEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [limit, setLimit] = useState(size);
  const [error, setError] = useState<string | null>(null);
  // 文言に潰す前の原因。呼び出し側が再試行を出すかどうかを決めるために返す
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // 同じフックで対象メンバーや limit が変わったとき、古い応答が新しい一覧を
  // 上書きしないよう、最後に開始したリクエストだけが state を更新する。
  const requestGeneration = useRef(0);

  // member が変わったら別の一覧になるので、広げた limit を持ち越さない。
  // entries も捨てる。残すと取得が終わるまで前のメンバーの行が並んだままになり、
  // 呼び出し側が「◯◯の変化だけを表示中」と出している最中に別人の行が見える
  useEffect(() => {
    setLimit(size);
    setEntries([]);
    setHasMore(false);
  }, [member, size]);

  const load = useCallback(async () => {
    const generation = ++requestGeneration.current;
    if (!enabled) return;
    setLoading(true);
    setError(null);
    setErrorCode(null);
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      // 空文字を送るとバックエンドは未指定として扱うが、そもそも送らない
      if (member) params.set("member", member);
      const res = await api.get<ChangeLogResponse>(
        `/projects/${projectId}/changelog?${params}`,
      );
      if (generation !== requestGeneration.current) return;
      setEntries(res.entries);
      setHasMore(res.has_more);
    } catch (e) {
      if (generation !== requestGeneration.current) return;
      setErrorCode(e instanceof ApiError ? (e.code ?? null) : null);
      setError(
        // GitHub由来の失敗は全部 502 に写るため、ステータスだけだと「サーバーで
        // エラーが発生しました」に潰れて原因の切り分けができない。code で分ける
        // （AGENTS.md「ステータスだけで区別できないドメインエラーは code で上書き」）
        messageForError(e, {
          codes: {
            REPO_NOT_FOUND:
              "GitHubリポジトリを読み取れませんでした。リポジトリへのアクセス権限を確認してください。",
            GITHUB_RATE_LIMITED:
              "GitHubの利用上限に達しました。しばらく待つと自動で解除されます。",
            GITHUB_FORBIDDEN:
              "GitHubがアクセスを拒否しました（利用上限の可能性があります）。しばらく待ってから開き直してください。",
            GITHUB_AUTH_FAILED:
              "GitHubとの連携が切れています。ログインし直してください。",
            GITHUB_TIMEOUT: "GitHubの応答がありませんでした。",
            GITHUB_UNAVAILABLE: "GitHubが応答していません。",
          },
          fallback: "変化ログの取得に失敗しました",
        }),
      );
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }, [projectId, member, limit, enabled]);

  useEffect(() => {
    void load();
    return () => {
      // 依存値が変わって次の load が始まるまでの間も、旧応答を無効にする。
      requestGeneration.current += 1;
    };
  }, [load]);

  const loadMore = useCallback(() => {
    setLimit((current) => Math.min(current + size, MAX_LIMIT));
  }, [size]);

  return {
    entries,
    // 上限に達していたら「続きがある」と言わない。言うと押せるボタンが出て、
    // 押した先に 422 しかない
    hasMore: hasMore && limit < MAX_LIMIT,
    // API が続きの存在を返したか。呼び出し側が集計の打ち切り表示に使う
    truncated: hasMore,
    error,
    errorCode,
    loading,
    loadMore,
    reload: load,
  };
}
