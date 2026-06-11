"use client";

import { Badge } from "@/components/ui/Badge";
import type { GitHubItem } from "@/types";
import styles from "./RecentItems.module.css";

const STATE_TONE: Record<string, "green" | "ochre" | "slate" | "neutral" | "red"> =
  {
    merged: "green",
    open: "ochre",
    closed: "neutral",
    approved: "green",
    changes_requested: "red",
    commented: "slate",
  };

type Props = {
  title: string;
  items: GitHubItem[];
  emptyText: string;
};

// スコアの根拠をGitHubへの直リンクで開示する（透明性の担保）
export function RecentItems({ title, items, emptyText }: Props) {
  return (
    <section className={styles.section}>
      <h3 className={styles.title}>{title}</h3>
      {items.length === 0 ? (
        <p className={styles.empty}>{emptyText}</p>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => (
            <li key={`${item.number}-${item.created_at}`}>
              <a
                className={styles.item}
                href={item.html_url}
                target="_blank"
                rel="noreferrer"
              >
                <span className={`num ${styles.number}`}>#{item.number}</span>
                <span className={styles.itemTitle}>{item.title}</span>
                {item.extra && <Badge tone="ochre">{item.extra}</Badge>}
                <Badge tone={STATE_TONE[item.state] ?? "neutral"}>
                  {item.state}
                </Badge>
                <span className={`num ${styles.date}`}>
                  {new Date(item.created_at).toLocaleDateString("ja-JP")}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
