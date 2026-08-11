"use client";

import { useEffect, useMemo, useState } from "react";
import { useChangeLog } from "@/hooks/useChangeLog";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import type { Member } from "@/types";
import { buildActivityWeeks, summarizeContribution } from "./activity";

/**
 * 変化ログの取得件数。既定（50）より深く取るのは、この画面が表示中の行を数えて
 * 件数と活動量を出しているため。50 だと活動的なメンバーで集計が打ち切りに引きずられ、
 * 「12週の推移」が数週分しか描けない。
 *
 * 上限を撤廃しないのは、打ち切られた事実を has_more で受け取って画面に明示できる
 * 形を保つため（キャッシュ自体も services/github.py の MAX_LIST_PAGES で頭打ち）。
 */
const PAGE_SIZE = 200;

const MAX_WEEKS = 12;

/**
 * メンバー詳細（画面5）のデータ取得。
 *
 * スコア（GET /scores）もAIサマリー（GET /summaries）も呼ばない。前者はこの画面に
 * 載せない方針（docs/scoring_design.md「Goodhart対策とスコアの事後開示」）、後者は
 * #16 の担当で、未生成・停止でも変化ログが出ることを完了条件にしているため。
 */
export function useMemberDetail(projectId: string, login: string, enabled = true) {
  const changelog = useChangeLog(projectId, {
    member: login,
    enabled,
    pageSize: PAGE_SIZE,
  });

  // 人を切り替える導線に使う顔ぶれ。変化ログ（1人分に絞ってある）からは作れないので
  // 既存の GET /projects/{id}/members を引く
  const [members, setMembers] = useState<Member[] | null>(null);
  const [membersError, setMembersError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    api
      .get<Member[]>(`/projects/${projectId}/members`)
      .then((data) => {
        if (!cancelled) setMembers(data);
      })
      .catch((e) => {
        if (!cancelled)
          setMembersError(
            messageForError(e, { fallback: "他のメンバーを読み込めませんでした" }),
          );
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, enabled]);

  const { entries, hasMore } = changelog;

  const facts = useMemo(() => summarizeContribution(entries), [entries]);

  const weeks = useMemo(
    () =>
      buildActivityWeeks(entries, new Date(), {
        maxWeeks: MAX_WEEKS,
        truncated: hasMore,
      }),
    [entries, hasMore],
  );

  return {
    changelog,
    facts,
    weeks,
    // 集計の母数と、それが全部かどうか。画面はこの2つをそのまま読み手に伝える
    countedEntries: entries.length,
    truncated: hasMore,
    members,
    membersError,
  };
}
