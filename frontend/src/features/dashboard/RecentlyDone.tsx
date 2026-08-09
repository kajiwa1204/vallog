"use client";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { DoneItem } from "@/types";
import styles from "./RecentlyDone.module.css";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/**
 * 最近片づいたもの。気にかけること（attention）の裏返し。
 *
 * attention は止まっているものしか出さないため、この画面は放っておくと負の情報だけを
 * 毎日見せる面になる。無給の有志チームでは進んだ実感が続ける理由になるので、
 * 同じデータの裏返しを並べて釣り合いを取る（docs/screen_design.md 画面4）。
 *
 * 人ごとの件数には畳まない。畳んだ瞬間に「誰が多いか」の序列になり、この画面が
 * 出さないと決めた集約に戻る（docs/scoring_design.md「数字の降格」）。
 */
export function RecentlyDone({ items }: { items: DoneItem[] }) {
  return (
    <Card
      title="最近片づいたもの"
      // 打ち切りを明示する。件数が出ないと「これで全部」と読める
      actions={
        items.length > 0 && (
          <span className={`num ${styles.count}`}>直近 {items.length} 件</span>
        )
      }
    >
      {items.length === 0 ? (
        <p className={styles.empty}>
          マージされたPRや完了したIssueがここに出ます
        </p>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => (
            <li key={`${item.kind}:${item.number}`}>
              <a
                className={styles.item}
                href={item.html_url}
                target="_blank"
                rel="noreferrer"
              >
                <div className={styles.head}>
                  {/* 語は ChangeLogList（共有プリミティブ）に合わせる。
                      同じ出来事が同じ画面で別の言葉になるのを避ける */}
                  <Badge tone="green">
                    {item.kind === "pull_request" ? "マージ済み" : "クローズ"}
                  </Badge>
                  <span className={`num ${styles.number}`}>#{item.number}</span>
                  <span className={styles.title}>{item.title}</span>
                </div>
                <div className={styles.meta}>
                  <span className={`num ${styles.who}`}>{item.actor_login}</span>
                  <span className={`num ${styles.when}`}>
                    {formatDate(item.occurred_at)}
                  </span>
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
