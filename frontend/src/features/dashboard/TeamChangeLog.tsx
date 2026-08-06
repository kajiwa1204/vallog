"use client";

import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { ChangeLogList } from "@/components/ChangeLogList";
import { Spinner } from "@/components/ui/Spinner";
import type { ChangeLogEntry } from "@/types";
import styles from "./TeamChangeLog.module.css";

type Props = {
  projectId: string;
  entries: ChangeLogEntry[];
  roster: string[];
  selected: string | null;
  onSelect: (login: string | null) => void;
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  onLoadMore: () => void;
  // 初回同期がまだ終わっていない。0件を「変化がない」と言い切らないために区別する
  syncing: boolean;
};

/**
 * ダッシュボードの主役（#13）。ChangeLogList を包み、絞り込みと状態表示を足す。
 *
 * 一覧そのものは components/ChangeLogList（#77）に委ね、ここは「誰で絞るか」と
 * 「取得中/同期中/空」の出し分けだけを持つ。
 */
export function TeamChangeLog({
  projectId,
  entries,
  roster,
  selected,
  onSelect,
  loading,
  error,
  hasMore,
  onLoadMore,
  syncing,
}: Props) {
  // 追加読み込みは limit を増やして取り直すため loading が立つ。既に行が見えている間は
  // 全体をスピナーに差し替えず、「もっと見る」だけを読み込み中にする
  const initialLoading = loading && entries.length === 0;

  return (
    <Card
      title="チームの変化"
      actions={
        <span className={styles.note}>
          GitHubの一次情報にそのまま飛べます
        </span>
      }
    >
      {roster.length > 0 && (
        <div className={styles.filters} role="group" aria-label="メンバーで絞り込む">
          <button
            type="button"
            className={`${styles.chip} ${selected === null ? styles.active : ""}`}
            onClick={() => onSelect(null)}
          >
            すべて
          </button>
          {roster.map((login) => (
            <button
              key={login}
              type="button"
              className={`${styles.chip} ${selected === login ? styles.active : ""}`}
              onClick={() => onSelect(selected === login ? null : login)}
            >
              <Avatar login={login} size={18} />
              <span className={`num ${styles.chipLogin}`}>{login}</span>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className={styles.selectedBar}>
          <span className={styles.selectedText}>
            <span className={`num ${styles.selectedLogin}`}>{selected}</span>{" "}
            の変化だけを表示中
          </span>
          <Link
            className={styles.detailLink}
            href={`/projects/${projectId}/members/${selected}`}
          >
            メンバー詳細 →
          </Link>
        </div>
      )}

      {error ? (
        <p className={styles.error}>{error}</p>
      ) : initialLoading ? (
        <Spinner label="GitHubから変化ログを読み込んでいます…" />
      ) : (
        <ChangeLogList
          entries={entries}
          emptyText={
            syncing
              ? "GitHubからの初回同期中です。数十秒かかることがあります。"
              : selected
                ? "この期間にこのメンバーの変化はありません"
                : "まだ変化がありません"
          }
          hasMore={hasMore}
          loadingMore={loading}
          onLoadMore={onLoadMore}
        />
      )}
    </Card>
  );
}
