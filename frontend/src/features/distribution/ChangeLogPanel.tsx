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
 * 分配画面の主役（第1層・#77）。チーム全員の変化ログをそのまま並べる。
 *
 * 上部に置くのは、分配の議論が**数字ではなく事実から始まる**ようにするため
 * （docs/scoring_design.md「チームはまず貢献サマリーを読んで議論し、スコアは
 * 補助情報として参照する」）。スコアは同じページの最下部にある。
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
        分配の話は、まずここに並ぶ事実から始めます。各行はGitHubの元のPR・Issue・レビューに直接開きます。
      </p>

      {error ? (
        <PanelError message={error} onRetry={onRetry} retrying={loading} />
      ) : loading && entries.length === 0 ? (
        <Spinner label="変化ログを読み込んでいます…" />
      ) : (
        <>
          <ChangeLogList
            entries={entries}
            emptyText="まだ変化がありません"
            hasMore={hasMore}
            loadingMore={loading}
            onLoadMore={onLoadMore}
          />
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
