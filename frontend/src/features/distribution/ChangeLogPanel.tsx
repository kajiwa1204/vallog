"use client";

import { ChangeLogList } from "@/components/ChangeLogList";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import type { ChangeLogEntry } from "@/types";
import { PanelError } from "./PanelError";
import styles from "./ChangeLogPanel.module.css";

type Props = {
  entries: ChangeLogEntry[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  atLimit: boolean;
  onLoadMore: () => void;
  /** 押しても状況が悪化するだけのエラーでは渡さない（利用上限など） */
  onRetry?: () => void;
};

/**
 * 分配画面の根拠（第1層・#77）。チーム全員の変化ログをそのまま並べる。
 *
 * 上の概観（スコアと貢献サマリー）で見た数字が、実際に何から来ているかを1件ずつ
 * 確かめる場所。各行がGitHubの元のPR・Issue・レビューに直接開くので、**この画面で
 * 唯一、外部で検証できる情報**になっている。
 *
 * 高さに上限を掛けて内部スクロールにしてある。既定で50件あり、伸びるままにすると
 * この画面で実際にやること（配分を決める）に着くまでのスクロールが長くなりすぎる。
 * 件数を減らして解決しないのは、議論中に遡って探す用途があるため。**縦に場所を
 * 取ることと、たくさん読めることは別の話**で、後者だけを残す。
 *
 * ダッシュボード（画面4）と違ってメンバーの絞り込みチップは置かない。分配は全員の
 * 貢献を並べて話す場なので、既定で全員が見えている必要がある。1人ずつ確かめたい
 * ときはメンバー詳細（画面5）が担う。
 */
export function ChangeLogPanel({
  entries,
  loading,
  error,
  hasMore,
  atLimit,
  onLoadMore,
  onRetry,
}: Props) {
  return (
    <Card title="チームの変化ログ">
      <p className={styles.lead}>
        上のスコアとサマリーが何から来ているかを1件ずつ確かめられます。各行はGitHubの元のPR・Issue・レビューに直接開きます。
      </p>

      {error ? (
        <PanelError message={error} onRetry={onRetry} retrying={loading} />
      ) : loading && entries.length === 0 ? (
        <Spinner label="変化ログを読み込んでいます…" />
      ) : (
        <>
          {/* 「もっと見る」もこの中に入る。外に出すと、押すたびに枠の外側が伸びて
              高さを抑えた意味がなくなる */}
          <div className={styles.scroll}>
            <ChangeLogList
              entries={entries}
              emptyText="まだ変化がありません"
              hasMore={hasMore}
              loadingMore={loading}
              onLoadMore={onLoadMore}
            />
          </div>
          {/* 「もっと見る」が消えた理由を言う。黙って消えると「全部見た」と読まれる */}
          {atLimit && (
            <p className={styles.limit}>
              この画面から読める上限（<span className="num">200</span>件）まで表示しています。これより古い変化はGitHubで確認してください。
            </p>
          )}
        </>
      )}
    </Card>
  );
}
