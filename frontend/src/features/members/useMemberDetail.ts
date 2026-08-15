"use client";

import { useEffect, useMemo, useState } from "react";
import { useChangeLog } from "@/hooks/useChangeLog";
import { api } from "@/lib/api";
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
  // 既存の GET /projects/{id}/members を引く。
  //
  // 失敗しても画面にエラーを出さない。この1本はGitHubのcontributorsを毎回叩く
  // （DBキャッシュを通らない）ため、トークンの権限が足りないプロジェクトでは
  // **開くたびに必ず失敗する**。ユーザーに打つ手が無い失敗を毎回見せると、
  // 「何かが壊れている」という誤ったシグナルが常態化する。顔ぶれが引けないときは
  // 切り替え欄ごと出さないほうが正直で、主軸（記録）には影響がない
  const [members, setMembers] = useState<Member[] | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    api
      .get<Member[]>(`/projects/${projectId}/members`)
      .then((data) => {
        if (!cancelled) setMembers(data);
      })
      .catch(() => {
        if (!cancelled) setMembers(null);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, enabled]);

  const { entries } = changelog;

  // サーバがまだ続きがあると言っている。もう取りに行けない（atLimit）場合も含めて
  // 「数えた範囲が全部ではない」ことに変わりはないので、まとめて打ち切り扱いにする
  const truncated = changelog.hasMore || changelog.atLimit;

  const facts = useMemo(
    () => summarizeContribution(entries, login),
    [entries, login],
  );

  const weeks = useMemo(
    () =>
      buildActivityWeeks(entries, new Date(), {
        maxWeeks: MAX_WEEKS,
        truncated,
      }),
    [entries, truncated],
  );

  // 一覧は occurred_at の降順なので先頭が最新。グラフの窓に1件も入らなかったときに
  // 「では記録はいつのものか」を答えるために使う
  const latestAt = entries.length > 0 ? entries[0].occurred_at : null;

  /**
   * このログインがプロジェクトの顔ぶれに居るか。顔ぶれを引けていなければ null（不明）。
   *
   * URLは共有される前提（「自分の記録を見せる」ための画面）なので、綴り違いや
   * 大文字小文字違いで開かれうる。バックエンドの絞り込みは大文字小文字を区別するため、
   * 実在しないログインは0件になり「記録が消えた」と見分けが付かない
   */
  const knownMember =
    members === null ? null : members.some((m) => m.github_login === login);

  return {
    changelog,
    facts,
    weeks,
    latestAt,
    // 集計の母数と、それが全部かどうか。画面はこの2つをそのまま読み手に伝える
    countedEntries: entries.length,
    truncated,
    members,
    knownMember,
  };
}
