import styles from "./SummaryText.module.css";
import { splitSummaryText } from "./summaryTextParser";

type Props = {
  content: string;
  repoOwner?: string;
  repoName?: string;
};

/** AI本文中の #番号をGitHubの一次情報へ結び、主張をその場で検証できる形にする。 */
export function SummaryText({ content, repoOwner, repoName }: Props) {
  const canLink = repoOwner !== undefined && repoName !== undefined;

  return (
    <p className={styles.content}>
      {splitSummaryText(content).map((part, index) => {
        if (part.type === "text" || !canLink) {
          return <span key={index}>{part.value}</span>;
        }
        return (
          <a
            key={index}
            className={styles.reference}
            href={`https://github.com/${encodeURIComponent(repoOwner)}/${encodeURIComponent(repoName)}/issues/${part.number}`}
            target="_blank"
            rel="noreferrer"
            aria-label={`${part.value}をGitHubで確認（新しいタブ）`}
          >
            {part.value}
          </a>
        );
      })}
    </p>
  );
}
