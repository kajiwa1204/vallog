"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { SummaryText } from "@/features/summaries/SummaryText";
import type { PRSummaryItem, Summary, SummaryJob } from "@/types";
import styles from "./ContributionSummary.module.css";

type Props = {
  repoOwner?: string;
  repoName?: string;
  summary: Summary | null;
  prs: PRSummaryItem[];
  memberJob: SummaryJob | null;
  loading: boolean;
  error: string | null;
  startingMember: boolean;
  startingPrs: number[];
  onGenerateMember: () => void;
  onGeneratePr: (prNumber: number) => void;
  onRetry: () => void;
};

function active(job: SummaryJob | null | undefined): boolean {
  return job?.status === "pending" || job?.status === "running";
}

function progress(job: SummaryJob): string {
  if (job.status === "pending") return "生成を待っています";
  if (job.status === "running") {
    return job.total_prs > 0
      ? `PRを要約中 ${job.done_prs}/${job.total_prs}`
      : "活動データを要約しています";
  }
  return job.status === "failed" ? "前回の生成に失敗しました" : "生成済み";
}

export function ContributionSummary({
  repoOwner,
  repoName,
  summary,
  prs,
  memberJob,
  loading,
  error,
  startingMember,
  startingPrs,
  onGenerateMember,
  onGeneratePr,
  onRetry,
}: Props) {
  const memberActive = active(memberJob);
  const anyPrActive = prs.some((pr) => active(pr.job));

  return (
    <Card
      title="貢献サマリー"
      actions={
        <Button
          variant="secondary"
          size="s"
          loading={startingMember || memberActive}
          disabled={loading || anyPrActive}
          title={
            anyPrActive ? "PR単位の生成が完了してから更新できます" : undefined
          }
          onClick={onGenerateMember}
        >
          {summary ? "全体を更新" : "全体を生成"}
        </Button>
      }
    >
      <p className={styles.lead}>
        AIによる説明です。本文の #番号と各PRへのリンクから、GitHubの一次情報を確認できます。
      </p>

      {error && <ErrorState message={error} onRetry={onRetry} retrying={loading} />}
      {!error && loading && <Spinner label="貢献サマリーを読み込んでいます…" />}

      {!loading && memberJob && memberJob.status !== "succeeded" && (
        <p
          className={memberJob.status === "failed" ? styles.failed : styles.status}
          role={memberJob.status === "failed" ? "alert" : "status"}
        >
          {progress(memberJob)}
        </p>
      )}

      {!loading && summary ? (
        <div className={styles.memberSummary}>
          <SummaryText
            content={summary.content}
            repoOwner={repoOwner}
            repoName={repoName}
          />
          <p className={`num ${styles.generated}`}>
            更新 {new Date(summary.generated_at).toLocaleString("ja-JP")}
          </p>
        </div>
      ) : (
        !loading &&
        !memberActive && (
          <p className={styles.empty}>
            まだ生成されていません。下の変化ログはAIを使わず表示されるため、生成前でも記録を確認できます。
          </p>
        )
      )}

      {!loading && prs.length > 0 && (
        <div className={styles.prSection}>
          <h3 className={styles.prTitle}>PRごとの要約と根拠</h3>
          <ul className={styles.prList}>
            {prs.map((pr) => {
              const prActive = active(pr.job);
              const starting = startingPrs.includes(pr.pr_number);
              return (
                <li key={pr.pr_number} className={styles.prItem}>
                  <div className={styles.prHead}>
                    <a
                      className={styles.prLink}
                      href={pr.html_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <span className="num">#{pr.pr_number}</span> {pr.title} ↗
                    </a>
                    <Button
                      variant="ghost"
                      size="s"
                      loading={starting || prActive}
                      disabled={memberActive}
                      title={
                        memberActive
                          ? "全体サマリーの生成が完了してから再生成できます"
                          : undefined
                      }
                      onClick={() => onGeneratePr(pr.pr_number)}
                    >
                      {pr.content ? "再生成" : "生成"}
                    </Button>
                  </div>
                  {pr.job?.status === "failed" && (
                    <p className={styles.failed} role="alert">
                      前回の生成に失敗しました。再生成できます。
                    </p>
                  )}
                  {pr.content ? (
                    <div className={styles.prContent}>
                      <SummaryText content={pr.content} />
                    </div>
                  ) : (
                    !prActive && (
                      <p className={styles.prEmpty}>このPRの要約は未生成です。</p>
                    )
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Card>
  );
}
