"use client";

import { Card } from "@/components/ui/Card";
import { ChangeLogList } from "@/components/ChangeLogList";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import type { ChangeLogEntry } from "@/types";
import styles from "./ChangeLog.module.css";

type Props = {
  login: string;
  // 本人が自分の記録を見ているか。文言を「あなた」に寄せるためだけに使う
  isMe: boolean;
  entries: ChangeLogEntry[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  onLoadMore: () => void;
  // 押しても状況を悪くするだけのエラー（利用上限など）のときは渡ってこない
  onRetry?: () => void;
  /**
   * このログインが取得できた貢献者一覧に居るか。null は一覧を引けず不明。
   *
   * false は綴り違いの手掛かりになるが、contributors API の取得範囲外もありうるため、
   * 実在しないとは断定しない
   */
  knownMember: boolean | null;
};

/**
 * メンバー詳細の主軸（#14）。ChangeLogList を包み、状態表示だけを足す。
 *
 * ダッシュボードの TeamChangeLog と違って絞り込みを持たない。この画面は最初から
 * 1人分に絞られていて、人の切り替えはページ上部の導線が担うため。
 *
 * 新着の印（newSince）も出さない。あれは「毎日開くダッシュボードで前回からの差分を
 * 拾う」ための仕掛けで、記録を遡って検算する画面では基準が意味を持たない。
 */
export function MemberChangeLog({
  login,
  isMe,
  entries,
  loading,
  error,
  hasMore,
  onLoadMore,
  onRetry,
  knownMember,
}: Props) {
  // 追加読み込み中は全体をスピナーに差し替えない（既に読めている行を消さない）
  const initialLoading = loading && entries.length === 0;

  return (
    <Card
      title={isMe ? "あなたの記録" : `${login} の記録`}
      actions={
        <span className={styles.note}>GitHubの一次情報にそのまま飛べます</span>
      }
    >
      {error ? (
        <ErrorState message={error} onRetry={onRetry} retrying={loading} />
      ) : initialLoading ? (
        <Spinner label="GitHubから記録を読み込んでいます…" />
      ) : (
        <ChangeLogList
          entries={entries}
          emptyText={
            knownMember === false
              ? `${login} の記録はまだありません。ユーザー名の綴り（大文字・小文字を含む）に間違いがないか確認してください。`
              : isMe
                ? "この期間にあなたの記録はまだありません"
                : `この期間に ${login} の記録はありません`
          }
          hasMore={hasMore}
          loadingMore={loading}
          onLoadMore={onLoadMore}
        />
      )}
    </Card>
  );
}
