"use client";

import { Button } from "@/components/ui/Button";
import type { ProposalListItem } from "@/types";
import styles from "./ProposalSwitcher.module.css";

type Props = {
  /** 検討中の案だけ。確定済み・削除済みは ProposalRecords が持つ */
  drafts: ProposalListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  comparing: boolean;
  onToggleCompare: () => void;
  /** 比較を出すかどうか。案が1件しかないと並べる相手がいない */
  canCompare: boolean;
  creating: boolean;
};

/**
 * 検討中の案の切り替えと新規作成。
 *
 * **確定済みの案はここに出さない。** 確定した案は編集も削除もできず、ここでできる
 * 操作が何も無い。分配を何度もまわすチームでは確定済みが溜まり続けるので、混ぜると
 * いま触るべき案がその中に埋もれる（確定25件・検討中2件で31チップが4段に折り返し、
 * 本文がその分だけ下に押し出されていた）。確定済みは下の「確定した分配」で読む。
 *
 * 並びはサーバの返す作成日時の降順のまま。案の「良さ」で並べ替えないのは、並び自体が
 * 推奨に読めるため。分配案の優劣を決めるのは人間の議論の側にある。
 */
export function ProposalSwitcher({
  drafts,
  selectedId,
  onSelect,
  onCreate,
  comparing,
  onToggleCompare,
  canCompare,
  creating,
}: Props) {
  return (
    <div className={styles.bar}>
      <div className={styles.tabs}>
        {drafts.length === 0 ? (
          <span className={styles.empty}>検討中の案はありません</span>
        ) : (
          drafts.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`${styles.tab} ${p.id === selectedId ? styles.active : ""}`}
              aria-current={p.id === selectedId ? "true" : undefined}
              onClick={() => onSelect(p.id)}
            >
              {p.name}
            </button>
          ))
        )}
      </div>

      <div className={styles.actions}>
        {canCompare && (
          <Button variant="ghost" size="s" onClick={onToggleCompare}>
            {comparing ? "比較を閉じる" : "案を並べて比較"}
          </Button>
        )}
        <Button variant="secondary" size="s" loading={creating} onClick={onCreate}>
          新しい案を作成
        </Button>
      </div>
    </div>
  );
}
