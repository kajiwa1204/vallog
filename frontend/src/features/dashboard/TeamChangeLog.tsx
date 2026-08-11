"use client";

import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { ChangeLogList } from "@/components/ChangeLogList";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import type { ChangeLogEntry } from "@/types";
import styles from "./TeamChangeLog.module.css";

type Props = {
  projectId: string;
  entries: ChangeLogEntry[];
  roster: string[];
  // ログイン中のユーザー。チップの先頭に固定して「自分の記録」に辿り着けるようにする
  me: string | null;
  selected: string | null;
  onSelect: (login: string | null) => void;
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  // 前回このダッシュボードを開いた時刻。これより後の変化に印を付ける
  newSince: string | null;
  onLoadMore: () => void;
  // エラーの出た場所で取り直せるようにする。ヘッダの再読み込みは画面最上部にあり、
  // 変化ログのエラーは最下部に出るので導線として遠い
  onRetry: () => void;
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
  me,
  selected,
  onSelect,
  loading,
  error,
  hasMore,
  newSince,
  onLoadMore,
  onRetry,
  syncing,
}: Props) {
  // 追加読み込みは limit を増やして取り直すため loading が立つ。既に行が見えている間は
  // 全体をスピナーに差し替えず、「もっと見る」だけを読み込み中にする
  const initialLoading = loading && entries.length === 0;

  // 自分だけ先頭に固定する。残りは辞書順のまま（活動量で並べ替えると、ダッシュボードが
  // 出さないはずの序列がチップに現れる）。自分の定位置は誰の画面でも先頭なので序列にならない
  const chips =
    me !== null && roster.includes(me)
      ? [me, ...roster.filter((login) => login !== me)]
      : roster;

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
          {/* 選択状態を色だけで示すと、読み上げでも色覚特性でも届かない。
              押下状態を持つボタンとして宣言する */}
          <button
            type="button"
            aria-pressed={selected === null}
            className={`${styles.chip} ${selected === null ? styles.active : ""}`}
            onClick={() => onSelect(null)}
          >
            すべて
          </button>
          {chips.map((login) => (
            <button
              key={login}
              type="button"
              aria-pressed={selected === login}
              className={`${styles.chip} ${selected === login ? styles.active : ""}`}
              onClick={() => onSelect(selected === login ? null : login)}
            >
              <Avatar login={login} size={18} />
              <span className={`num ${styles.chipLogin}`}>{login}</span>
              {login === me && <span className={styles.chipMine}>あなた</span>}
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
          {/* 絞り込みは「この人の分だけ見る」で、詳細は「この人の記録を数と推移まで
              辿る」。同じ関心の続きなので、絞り込んだその場から飛べるようにする */}
          <Link
            className={styles.detailLink}
            href={`/projects/${projectId}/members/${encodeURIComponent(selected)}`}
          >
            メンバー詳細 →
          </Link>
        </div>
      )}

      {error ? (
        <ErrorState message={error} onRetry={onRetry} retrying={loading} />
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
          newSince={newSince}
          loadingMore={loading}
          onLoadMore={onLoadMore}
        />
      )}
    </Card>
  );
}
