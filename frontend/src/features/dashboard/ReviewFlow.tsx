"use client";

import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import type { ReviewEdge } from "@/types";
import styles from "./ReviewFlow.module.css";

const VISIBLE = 8;

/**
 * レビューの流れ（collaboration）。誰が誰の仕事を見ているか。
 *
 * 件数は多い/少ないの評価ではなく、レビューが特定の人に寄っていないかを見るためのもの。
 */
export function ReviewFlow({ edges }: { edges: ReviewEdge[] }) {
  const shown = edges.slice(0, VISIBLE);
  const max = Math.max(...shown.map((e) => e.count), 1);

  return (
    <Card
      title="レビューの流れ"
      actions={
        edges.length > VISIBLE && (
          <span className={`num ${styles.more}`}>ほか{edges.length - VISIBLE}組</span>
        )
      }
    >
      {shown.length === 0 ? (
        <p className={styles.empty}>まだレビューのやり取りがありません</p>
      ) : (
        <ul className={styles.list}>
          {shown.map((edge) => (
            <li
              key={`${edge.reviewer_login}->${edge.author_login}`}
              className={styles.row}
            >
              <span className={styles.pair}>
                <Avatar login={edge.reviewer_login} size={20} />
                <span className={`num ${styles.login}`}>
                  {edge.reviewer_login}
                </span>
                <span className={styles.arrow} aria-label="がレビューした相手">
                  →
                </span>
                <Avatar login={edge.author_login} size={20} />
                <span className={`num ${styles.login}`}>
                  {edge.author_login}
                </span>
              </span>
              <span className={styles.track}>
                <span
                  className={styles.bar}
                  style={{ width: `${(edge.count / max) * 100}%` }}
                />
              </span>
              <span className={`num ${styles.count}`}>{edge.count}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
