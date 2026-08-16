"use client";

import { useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import type { Proposal, ProposalListItem } from "@/types";
import { amountFor, formatAmount, formatPercent, toTenths } from "./allocation";
import { PanelError } from "./PanelError";
import styles from "./FinalizedProposals.module.css";

/**
 * 一度に描く件数。分配を毎月まわすチームでは年に12件ずつ増えるので、全部並べると
 * このカードだけで画面が埋まる。サーバ側のページングを入れていないのは、一覧の
 * レスポンスが1件あたり数フィールドと軽く、**描画の量だけが問題**だから。件数が
 * 実運用で数百に届くようなら、そのとき `GET /distributions` にページングを足す。
 */
const PAGE = 10;

type Props = {
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
          const tenths = toTenths(item.ratio);
          const amount = amountFor(proposal.total_amount, tenths);
          return (
            <tr key={item.github_login}>
              <th scope="row" className={styles.member}>
                <Avatar login={item.github_login} url={item.avatar_url} size={20} />
                <span className="num">{item.github_login}</span>
              </th>
              <td className={`num ${styles.percent}`}>{formatPercent(tenths)}%</td>
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
 * 確定した分配の履歴。
 *
 * 確定済みの案は編集も削除もできないので、検討中の案と同じ切り替えバーに混ぜると
 * 「触れないものが触れるものを押しのける」状態になる。長期に何度も分配するチーム
 * （複数の賞金を順に分配する使い方）では確定済みが溜まり続けるため、読むための面を
 * 分けて畳んでおく。
 *
 * 配分は開いたときに取りに行く。一覧APIは配分値を返さないので案ごとに1本必要で、
 * 全件をまとめて取ると開いてもいない案の分まで飛ぶ。
 */
export function FinalizedProposals({
  items,
  details,
  pendingIds,
  errorById,
  onOpen,
}: Props) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [shown, setShown] = useState(PAGE);

  if (items.length === 0) return null;

  const toggle = (id: string) => {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    if (!details[id]) onOpen(id);
  };

  return (
    <Card title="確定した分配">
      <p className={styles.lead}>
        合意して確定した分配の記録です。確定後は編集も削除もできません。
      </p>

      <ul className={styles.list}>
        {items.slice(0, shown).map((p) => {
          const open = openId === p.id;
          return (
            <li key={p.id} className={styles.item}>
              <button
                type="button"
                className={styles.head}
                aria-expanded={open}
                onClick={() => toggle(p.id)}
              >
                <span className={styles.marker} aria-hidden="true">
                  {open ? "▾" : "▸"}
                </span>
                <span className={styles.name}>{p.name}</span>
                <span className={`num ${styles.total}`}>
                  {p.total_amount === null
                    ? "割合のみ"
                    : `¥${formatAmount(Number(p.total_amount))}`}
                </span>
                <span className={`num ${styles.at}`}>
                  {p.finalized_at
                    ? new Date(p.finalized_at).toLocaleDateString("ja-JP")
                    : "—"}
                </span>
                {/* 確定した人が誰かは合意の記録の一部。退会済みでも欄は残す */}
                <span className={`num ${styles.by}`}>
                  {p.created_by_github_login ?? "（退会済み）"}
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
          <Button
            variant="ghost"
            size="s"
            onClick={() => setShown((n) => n + PAGE)}
          >
            さらに表示（残り {items.length - shown} 件）
          </Button>
        </div>
      )}
    </Card>
  );
}
