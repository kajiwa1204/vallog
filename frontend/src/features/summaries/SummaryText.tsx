import styles from "./SummaryText.module.css";

type Props = {
  content: string;
  repoOwner?: string;
  repoName?: string;
};

const REFERENCE = /(#\d+)/g;

/** AI本文中の #番号をGitHubの一次情報へ結び、主張をその場で検証できる形にする。 */
export function SummaryText({ content, repoOwner, repoName }: Props) {
  const canLink = repoOwner !== undefined && repoName !== undefined;

  return (
    <p className={styles.content}>
      {content.split(REFERENCE).map((part, index) => {
        const number = /^#(\d+)$/.exec(part)?.[1];
        if (!number || !canLink) return <span key={`${index}:${part}`}>{part}</span>;
        return (
          <a
            key={`${index}:${part}`}
            className={styles.reference}
            href={`https://github.com/${encodeURIComponent(repoOwner)}/${encodeURIComponent(repoName)}/issues/${number}`}
            target="_blank"
            rel="noreferrer"
            aria-label={`${part}をGitHubで確認（新しいタブ）`}
          >
            {part}
          </a>
        );
      })}
    </p>
  );
}
