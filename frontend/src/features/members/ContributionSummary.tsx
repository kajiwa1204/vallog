import styles from "./ContributionSummary.module.css";
import type { ContributionSummary as Summary } from "@/types";
import { Badge } from "@/components/ui/Badge";

type Props = { summary: Summary; repository: string };

const typeLabel: Record<string, string> = {
  pr: "PR",
  issue: "Issue",
  review: "Review",
};

const formatDate = (iso?: string) =>
  iso ? new Date(iso).toLocaleDateString("ja-JP", { month: "short", day: "numeric" }) : "—";

export function ContributionSummary({ summary, repository }: Props) {
  return (
    <div className={styles.wrapper}>
      <div className={styles.aiHead}>
        <span className={styles.aiBadge}>
          <span className={styles.aiDot} />
          Claude AIによる要約
        </span>
        <span className={styles.aiNote}>※ 評価ではなく、貢献の記録としての要約です</span>
      </div>
      <p className={styles.summary}>{summary.summary}</p>
      <ul className={styles.highlights}>
        {summary.highlights.map((h, i) => (
          <li key={i}>
            <span className={styles.highlightMark}>◆</span>
            <span>{h}</span>
          </li>
        ))}
      </ul>

      <div className={styles.itemsHead}>
        <h3 className={styles.itemsTitle}>根拠データ</h3>
        <span className={styles.itemsHint}>GitHubに直リンクします</span>
      </div>
      <ul className={styles.items}>
        {summary.items.map((item) => (
          <li key={`${item.type}-${item.number}`} className={styles.item}>
            <Badge tone={item.type === "pr" ? "accent" : item.type === "review" ? "default" : "warn"}>
              {typeLabel[item.type]}
            </Badge>
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className={styles.itemTitle}
            >
              {item.title}
            </a>
            <span className={styles.itemMeta}>
              {repository}#{item.number} ・ {formatDate(item.mergedAt)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
