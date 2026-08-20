"use client";

import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import type { Summary } from "@/types";
import styles from "./SummaryPanel.module.css";

type Props = {
  summaries: Summary[] | null;
};

/**
 * 貢献サマリー（第2層・Feature D）。**読み取り専用。**
 *
 * 変化ログ（第1層）の詳細として、生成済みのサマリーを展開する。生成の起動・進捗表示は
 * #16 の担当なのでここには置かない。未生成でも上の変化ログだけで議論は成り立つので、
 * 無いときは無いと言うに留める。
 *
 * サマリーはAIが書いた文章なので、根拠は必ず上の変化ログ側にある。ここを主役にすると、
 * 検証できない要約の上で分配を決めることになる。
 */
export function SummaryPanel({ summaries }: Props) {
  const items = summaries ?? [];

  return (
    <Card title="貢献サマリー">
      <p className={styles.lead}>
        メンバーごとの活動をAIが要約したものです。数字ではなく事実の説明なので、気になった記述は下の変化ログの該当行から元のPR・Issueで確かめられます。
      </p>

      {items.length === 0 ? (
        <p className={styles.empty}>
          まだ生成されたサマリーがありません。
          生成機能は準備中で、それまでは下の変化ログが根拠になります。
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
                <p className={styles.content}>{summary.content}</p>
              </details>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
