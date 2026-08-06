"use client";

import { Card } from "@/components/ui/Card";
import type { Theme } from "@/types";
import styles from "./Themes.module.css";

const VISIBLE = 8;

/**
 * 動いている領域（themes）。Issueのラベル集計。
 *
 * SPラベル（SP:1〜）はストーリーポイントであって領域ではないため、
 * バックエンド側で落としてある。
 */
export function Themes({ themes }: { themes: Theme[] }) {
  const shown = themes.slice(0, VISIBLE);
  const max = Math.max(...shown.map((t) => t.open_count + t.closed_count), 1);

  return (
    <Card
      title="動いている領域"
      actions={
        themes.length > VISIBLE && (
          <span className={`num ${styles.more}`}>
            ほか{themes.length - VISIBLE}種
          </span>
        )
      }
    >
      {shown.length === 0 ? (
        <p className={styles.empty}>
          Issueにラベルが付くと、どの領域が動いているかが出ます
        </p>
      ) : (
        <ul className={styles.list}>
          {shown.map((theme) => {
            const total = theme.open_count + theme.closed_count;
            return (
              <li key={theme.label} className={styles.row}>
                <span className={styles.label} title={theme.label}>
                  {theme.label}
                </span>
                <span className={styles.track}>
                  <span
                    className={styles.bar}
                    style={{ width: `${(total / max) * 100}%` }}
                  >
                    <span
                      className={styles.open}
                      style={{ flexGrow: theme.open_count }}
                    />
                    <span
                      className={styles.closed}
                      style={{ flexGrow: theme.closed_count }}
                    />
                  </span>
                </span>
                <span className={`num ${styles.counts}`}>
                  <span className={styles.openCount}>{theme.open_count}</span>
                  <span className={styles.slash}>/</span>
                  {total}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {shown.length > 0 && (
        <p className={styles.caption}>
          <span className={styles.swatchOpen} />
          オープン
          <span className={styles.swatchClosed} />
          クローズ
        </p>
      )}
    </Card>
  );
}
