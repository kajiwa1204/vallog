"use client";

import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import type { Member, Summary, SummaryJob } from "@/types";
import { SummaryJobFailure } from "./SummaryJobFailure";
import { SummaryText } from "./SummaryText";
import styles from "./SummaryList.module.css";

type Props = {
  projectId: string;
  repoOwner?: string;
  repoName?: string;
  members: Member[];
  summariesByLogin: Map<string, Summary>;
  jobsByLogin: Map<string, SummaryJob>;
  startingLogins: string[];
  generatingAll: boolean;
  unchangedLogins: string[];
  generationDisabled: boolean;
  onGenerate: (login: string) => void;
};

function jobLabel(job: SummaryJob | undefined): string | null {
  if (!job) return null;
  if (job.status === "pending") return "生成を待っています";
  if (job.status === "running") {
    return job.total_prs > 0
      ? `PRを要約中 ${job.done_prs}/${job.total_prs}`
      : "活動データを要約しています";
  }
  return null;
}

export function SummaryList({
  projectId,
  repoOwner,
  repoName,
  members,
  summariesByLogin,
  jobsByLogin,
  startingLogins,
  generatingAll,
  unchangedLogins,
  generationDisabled,
  onGenerate,
}: Props) {
  if (members.length === 0) {
    return (
      <div className={styles.empty}>
        <p>サマリーを作成できる貢献者がまだいません。</p>
        <p>GitHubでPRやIssueが記録されると、ここにメンバーが並びます。</p>
      </div>
    );
  }

  return (
    <ul className={styles.list}>
      {members.map((member) => {
        const summary = summariesByLogin.get(member.github_login);
        const job = jobsByLogin.get(member.github_login);
        const active = job?.status === "pending" || job?.status === "running";
        const status = jobLabel(job);
        const starting = startingLogins.includes(member.github_login);

        return (
          <li key={member.github_login} className={styles.item}>
            <header className={styles.head}>
              <Link
                className={styles.identity}
                href={`/projects/${projectId}/members/${encodeURIComponent(member.github_login)}`}
              >
                <Avatar
                  login={member.github_login}
                  url={member.avatar_url}
                  size={30}
                />
                <span className={`num ${styles.login}`}>
                  {member.github_login}
                </span>
              </Link>
              <Button
                variant="secondary"
                size="s"
                loading={generatingAll || starting || active}
                disabled={generationDisabled}
                onClick={() => onGenerate(member.github_login)}
              >
                {summary ? "更新する" : "生成する"}
              </Button>
            </header>

            {status && (
              <p className={styles.status}>{status}</p>
            )}
            {job?.status === "failed" && (
              <SummaryJobFailure job={job} className={styles.failed} />
            )}
            {unchangedLogins.includes(member.github_login) && (
              <p className={styles.unchanged} role="status">
                要約対象の内容に変更はありませんでした。サマリーは最新です。
              </p>
            )}

            {summary ? (
              <div className={styles.summary}>
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
              !active && (
                <p className={styles.notGenerated}>
                  まだ生成されていません。生成しても、GitHubの変化ログと生データは影響を受けません。
                </p>
              )
            )}
          </li>
        );
      })}
    </ul>
  );
}
