"use client";

import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { SummaryText } from "@/features/summaries/SummaryText";
import type { Summary } from "@/types";
import styles from "./SummaryPanel.module.css";

type Props = {
  projectId: string;
  repoOwner?: string;
  repoName?: string;
  summaries: Summary[] | null;
};

/**
 * 貢献サマリー（第2層・Feature D）。**読み取り専用。**
 *
 * 生成済みのサマリーを分配の概観として展開する。生成の起動・進捗表示は専用の
 * 貢献サマリー画面と画面5に置き、このパネルは議論中の読み取りに集中する。
 *
 * サマリーはAIが書いた文章なので、#番号をGitHubへ、メンバー名を画面5へ結ぶ。
 * ここを検証不能な文章だけにすると、要約の上で分配を決めることになるため。
 */
export function SummaryPanel({
  projectId,
  repoOwner,
  repoName,
  summaries,
}: Props) {
  const items = summaries ?? [];

  return (
    <Card title="貢献サマリー">
      <p className={styles.lead}>
        メンバーごとの活動をAIが要約したものです。本文の #番号やメンバー詳細から、元のPR・Issueを確認できます。
      </p>

      {items.length === 0 ? (
        <p className={styles.empty}>
          まだ生成されたサマリーがありません。
          <Link
            className={styles.manageLink}
            href={`/projects/${projectId}/summaries`}
          >
            貢献サマリー画面で生成する
          </Link>
        </p>
      ) : (
        <ul className={styles.list}>
          {items.map((summary) => (
            <li key={summary.github_login} className={styles.item}>
              <details>
                <summary className={styles.head}>
                  <Avatar login={summary.github_login} size={22} />
                  <span className={`num ${styles.login}`}>{summary.github_login}</span>
                  <span className={`num ${styles.at}`}>
                    {new Date(summary.generated_at).toLocaleDateString("ja-JP")}
                  </span>
                </summary>
                <div className={styles.content}>
                  <SummaryText
                    content={summary.content}
                    repoOwner={repoOwner}
                    repoName={repoName}
                  />
                  <Link
                    className={styles.memberLink}
                    href={`/projects/${projectId}/members/${encodeURIComponent(summary.github_login)}`}
                  >
                    このメンバーの記録を見る →
                  </Link>
                </div>
              </details>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
