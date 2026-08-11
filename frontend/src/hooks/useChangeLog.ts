"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { ChangeLogEntry, ChangeLogResponse } from "@/types";

// バックエンドの既定値と揃える（backend/app/services/changelog.py の DEFAULT_LIMIT）
const PAGE_SIZE = 50;

type Options = {
  // 未指定ならチーム全体。指定するとそのメンバーの変化だけに絞る（画面5・7）
  member?: string;
  // enabled=false の間は取得を保留する（認証確定前の無駄な 401 往復を避ける）
  enabled?: boolean;
  // 1回に取る件数。画面5は表示中の行から件数や活動量を数えるため、既定より深く
  // 取らないと集計が打ち切りに引きずられる。「もっと見る」の刻みも同じ値になる
  pageSize?: number;
};

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
  const [entries, setEntries] = useState<ChangeLogEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [limit, setLimit] = useState(pageSize);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // member が変わったら別の一覧になるので、広げた limit を持ち越さない。
  // entries も捨てる。残すと取得が終わるまで前のメンバーの行が並んだままになり、
  // 呼び出し側が「◯◯の変化だけを表示中」と出している最中に別人の行が見える
  useEffect(() => {
    setLimit(pageSize);
    setEntries([]);
    setHasMore(false);
  }, [member, pageSize]);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      // 空文字を送るとバックエンドは未指定として扱うが、そもそも送らない
      if (member) params.set("member", member);
      const res = await api.get<ChangeLogResponse>(
        `/projects/${projectId}/changelog?${params}`,
      );
      setEntries(res.entries);
      setHasMore(res.has_more);
    } catch (e) {
      setError(messageForError(e, { fallback: "変化ログの取得に失敗しました" }));
    } finally {
      setLoading(false);
    }
  }, [projectId, member, limit, enabled]);

  useEffect(() => {
    load();
  }, [load]);

  const loadMore = useCallback(() => {
    setLimit((current) => current + pageSize);
  }, [pageSize]);

  return { entries, hasMore, error, loading, loadMore, reload: load };
}
