"use client";

import { Button } from "@/components/ui/Button";
import type { ProposalListItem } from "@/types";
import styles from "./ProposalSwitcher.module.css";

type Props = {
  proposals: ProposalListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  comparing: boolean;
  onToggleCompare: () => void;
  creating: boolean;
};

/**
 * 案の切り替えと新規作成。
 *
 * 案を作る操作が**スコアの開示スイッチも兼ねている**（#100）。ここが分配の議論を
 * 始める入口なので、案が0件のときはこのバーに作成ボタンだけを出す。
 *
 * 並びはサーバの返す作成日時の降順のまま。案の「良さ」で並べ替えないのは、
 * 並び自体が推奨に読めるため。分配案の優劣を決めるのは人間の議論の側にある。
 */
export function ProposalSwitcher({
  proposals,
  selectedId,
  onSelect,
  onCreate,
  comparing,
  onToggleCompare,
  creating,
}: Props) {
  return (
    <div className={styles.bar}>
      <div className={styles.tabs}>
        {proposals.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`${styles.tab} ${p.id === selectedId ? styles.active : ""}`}
            aria-current={p.id === selectedId ? "true" : undefined}
            onClick={() => onSelect(p.id)}
          >
            {p.name}
            {p.finalized && (
              <span className={styles.finalized} title="確定済み">
                確定
              </span>
            )}
          </button>
        ))}
      </div>

      <div className={styles.actions}>
        {/* 1件しかないときの「比較」は押しても同じ表が1列出るだけ */}
        {proposals.length > 1 && (
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
