import Link from "next/link";
import styles from "./ContributionContext.module.css";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { mockScores, mockSummaries } from "@/lib/mockData";

type Props = { projectId: string };

export function ContributionContext({ projectId }: Props) {
  const sorted = [...mockScores].sort((a, b) => b.total - a.total);

  return (
    <div className={styles.wrapper}>
      <div className={styles.head}>
        <div>
          <h3 className={styles.title}>分配の根拠 — メンバー別の貢献</h3>
          <p className={styles.lead}>
            数字だけで決めずに、各メンバーが何をしたかを確認したうえで合意してください。
            <span className={styles.aiTag}>
              <span className={styles.aiDot} />
              AI生成サマリー
            </span>
          </p>
        </div>
      </div>

      <div className={styles.grid}>
        {sorted.map((score, idx) => {
          const summary = mockSummaries[score.login];
          if (!summary) return null;
          return (
            <article key={score.login} className={styles.card}>
              <header className={styles.cardHead}>
                <span className={styles.rank}>#{idx + 1}</span>
                <Avatar src={score.avatarUrl} alt={score.name} size={36} />
                <div className={styles.id}>
                  <div className={styles.name}>{score.name}</div>
                  <div className={styles.login}>@{score.login}</div>
                </div>
                <div className={styles.scoreBox}>
                  <div className={styles.scoreValue}>{score.total}</div>
                  <div className={styles.scoreLabel}>pts</div>
                </div>
              </header>

              <p className={styles.summary}>{summary.summary}</p>

              <ul className={styles.highlights}>
                {summary.highlights.map((h, i) => (
                  <li key={i}>
                    <span className={styles.highlightMark}>◆</span>
                    <span>{h}</span>
                  </li>
                ))}
              </ul>

              <footer className={styles.cardFoot}>
                <div className={styles.evidence}>
                  <Badge tone="muted">{summary.items.length} 件の根拠</Badge>
                  <div className={styles.metaList}>
                    <span>📦 {score.counts.prsMerged} PR</span>
                    <span>👁 {score.counts.reviewsGiven} Review</span>
                    <span>🏷 {score.counts.spTotal} SP</span>
                  </div>
                </div>
                <Link
                  href={`/projects/${projectId}/members/${score.login}`}
                  className={styles.detailLink}
                >
                  詳細を見る →
                </Link>
              </footer>
            </article>
          );
        })}
      </div>
    </div>
  );
}
