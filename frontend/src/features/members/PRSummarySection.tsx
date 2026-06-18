"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { PRSummaryItem } from "@/types";
import { usePRSummaries } from "./usePRSummaries";
import styles from "./PRSummarySection.module.css";

type Props = {
  projectId: string;
  login: string;
};

type StateBadgeProps = { state: PRSummaryItem["state"] };

function StateBadge({ state }: StateBadgeProps) {
  switch (state) {
    case "merged":
      return <Badge tone="green">merged</Badge>;
    case "open":
      return <Badge tone="slate">open</Badge>;
    case "draft":
      return <Badge>draft</Badge>;
    case "closed":
      return <Badge>closed</Badge>;
  }
}

type PRRowProps = {
  item: PRSummaryItem;
  onGenerate: (prNumber: number) => Promise<void>;
};

function PRRow({ item, onGenerate }: PRRowProps) {
  const [busy, setBusy] = useState(false);

  const isActive =
    item.job?.status === "pending" || item.job?.status === "running";
  const hasContent = item.content !== null;

  const handleGenerate = async () => {
    setBusy(true);
    try {
      await onGenerate(item.pr_number);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={styles.item}>
      <div className={styles.prHeader}>
        <div className={styles.prMeta}>
          <a
            href={item.html_url}
            target="_blank"
            rel="noreferrer"
            className={`num ${styles.prNumber}`}
          >
            #{item.pr_number}
          </a>
          <StateBadge state={item.state} />
          <span className={styles.prTitle}>{item.title}</span>
        </div>
        <div className={styles.prActions}>
          {item.generated_at && (
            <span className={`num ${styles.generatedAt}`}>
              {new Date(item.generated_at).toLocaleDateString("ja-JP")}
            </span>
          )}
          <Button
            variant="secondary"
            size="s"
            onClick={handleGenerate}
            loading={busy || isActive}
            disabled={busy || isActive}
          >
            {busy || isActive ? "生成中…" : hasContent ? "再生成" : "生成"}
          </Button>
        </div>
      </div>

      {item.job?.status === "failed" && item.job.error && (
        <p className={styles.jobError}>{item.job.error}</p>
      )}

      {hasContent && (
        <details className={styles.contentDetails}>
          <summary className={styles.contentSummary}>要約を見る</summary>
          <p className={styles.content}>{item.content}</p>
        </details>
      )}
    </li>
  );
}

// PRごとの貢献サマリーセクション。未生成PRも表示して個別生成を促す
export function PRSummarySection({ projectId, login }: Props) {
  const { items, loading, error, generatePrSummary } = usePRSummaries(
    projectId,
    login,
  );

  if (loading) return null;
  if (error) return <p className={styles.error}>{error}</p>;
  if (items.length === 0) return null;

  return (
    <details className={styles.details}>
      <summary className={styles.summary}>
        PRごとの貢献（
        <span className="num">{items.length}</span>件）
      </summary>
      <ul className={styles.list}>
        {items.map((item) => (
          <PRRow key={item.pr_number} item={item} onGenerate={generatePrSummary} />
        ))}
      </ul>
    </details>
  );
}
