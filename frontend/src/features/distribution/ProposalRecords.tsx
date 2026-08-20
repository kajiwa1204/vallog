"use client";

import { useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import type { Proposal, ProposalListItem } from "@/types";
import { formatAmount, formatPercent, toTenths } from "./allocation";
import { PanelError } from "./PanelError";
import styles from "./ProposalRecords.module.css";

/**
 * 一度に描く件数。分配を毎月まわすチームでは年に十数件ずつ増えるので、全部並べると
 * このカードだけで画面が埋まる。サーバ側のページングを入れていないのは、一覧の
 * レスポンスが1件あたり数フィールドと軽く、**描画の量だけが問題**だから。件数が
 * 実運用で数百に届くようなら、そのとき `GET /distributions` にページングを足す。
 */
const PAGE = 10;

type Props = {
  /** 確定済みと削除済み。どちらも「もう触れない過去の案」 */
  items: ProposalListItem[];
  /** 開いた案の配分。呼び出し側がキャッシュを持つ */
  details: Record<string, Proposal>;
  pendingIds: string[];
  errorById: Record<string, string>;
  onOpen: (proposalId: string) => void;
};

function Allocation({ proposal }: { proposal: Proposal }) {
  return (
    <table className={styles.table}>
      <tbody>
        {proposal.items.map((item) => {
          // 記録なので、サーバが返す金額をそのまま出す。比率から計算し直すと、
          // 編集不能な記録なのに開くたび画面の金額が記録と違うことになる
          const amount = item.amount === null ? null : Number(item.amount);
          return (
            <tr key={item.github_login}>
              <th scope="row">
                {/* flex はセルではなく内側に当てる（AllocationTable と同じ理由） */}
                <span className={styles.member}>
                  <Avatar login={item.github_login} url={item.avatar_url} size={20} />
                  <span className="num">{item.github_login}</span>
                </span>
              </th>
              <td className={`num ${styles.percent}`}>
                {formatPercent(toTenths(item.ratio))}%
              </td>
              <td className={`num ${styles.amount}`}>
                {amount === null ? "—" : `¥${formatAmount(amount)}`}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/**
 * 分配の記録（確定済み・削除済み）。
 *
 * 触れない案を切り替えバーに混ぜると、いま触るべき検討中の案がその中に埋もれる
 * （実測: 確定25件・検討中2件で切り替えバーが4段になった）。読むための面を分けて畳む。
 *
 * **削除された案もここに残す。** #100 の社会的抑止は「created_by が記録され編集履歴が
 * 全員に公開されるため、見えるかたちで意図的な行為をする必要がある」ことで成り立って
 * いるので、消したら一覧からも消える形だと「案を作ってスコアを読んで消す」で痕跡が
 * ゼロになり、抑止の根拠自体が無くなる。
 *
 * 配分は開いたときに取りに行く。一覧APIは配分値を返さないので案ごとに1本必要で、
 * 全件をまとめて取ると開いてもいない案の分まで飛ぶ。
 */
export function ProposalRecords({
  items,
  details,
  pendingIds,
  errorById,
  onOpen,
}: Props) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [shown, setShown] = useState(PAGE);

  if (items.length === 0) return null;

  const toggle = (id: string, removed: boolean) => {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    // 削除済みの案は詳細APIが404を返す（取得・編集の対象から外してある）。
    // 取りに行くとエラー表示になるので、記録として持っている情報だけを出す
    if (!details[id] && !removed) onOpen(id);
  };

  return (
    <Card title="分配の記録">
      <p className={styles.lead}>
        合意して確定した分配と、検討の途中で削除された案です。確定した分配は編集も削除もできません。
      </p>

      {/* 見出しが無いと、末尾に並ぶ名前が作成者なのか確定者なのか読めない */}
      <div className={`${styles.head} ${styles.columns}`} aria-hidden="true">
        <span />
        <span>案の名前</span>
        <span className={styles.right}>報酬総額</span>
        <span className={styles.right}>日付</span>
        <span className={styles.right}>操作した人</span>
      </div>

      <ul className={styles.list}>
        {items.slice(0, shown).map((p) => {
          const open = openId === p.id;
          const removed = p.deleted_at !== null;
          // 確定した人は作成者と別人になりうる。合意の記録として誰が確定したかを出す
          const actor = removed
            ? p.deleted_by_github_login
            : p.finalized_by_github_login;
          const at = removed ? p.deleted_at : p.finalized_at;
          return (
            <li key={p.id} className={styles.item}>
              <button
                type="button"
                className={styles.head}
                aria-expanded={open}
                onClick={() => toggle(p.id, removed)}
              >
                <span className={styles.marker} aria-hidden="true">
                  {open ? "▾" : "▸"}
                </span>
                <span className={styles.name}>
                  {p.name}
                  {removed && <span className={styles.removed}>削除済み</span>}
                </span>
                <span className={`num ${styles.total}`}>
                  {p.total_amount === null
                    ? "割合のみ"
                    : `¥${formatAmount(Number(p.total_amount))}`}
                </span>
                <span className={`num ${styles.at}`}>
                  {at ? new Date(at).toLocaleDateString("ja-JP") : "—"}
                </span>
                <span className={`num ${styles.by}`}>
                  {actor ?? "（退会済み）"}
                </span>
              </button>

              {open && (
                <div className={styles.body}>
                  {errorById[p.id] ? (
                    <PanelError
                      message={errorById[p.id]}
                      onRetry={() => onOpen(p.id)}
                      retrying={pendingIds.includes(p.id)}
                    />
                  ) : details[p.id] ? (
                    <Allocation proposal={details[p.id]} />
                  ) : removed ? (
                    <p className={styles.removedNote}>
                      削除された案の配分は表示しません。誰がいつ削除したかだけを記録として残しています。
                    </p>
                  ) : (
                    <Spinner label="配分を読み込んでいます…" />
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {items.length > shown && (
        <div className={styles.more}>
          <Button variant="ghost" size="s" onClick={() => setShown((n) => n + PAGE)}>
            さらに表示（残り {items.length - shown} 件）
          </Button>
        </div>
      )}
    </Card>
  );
}
