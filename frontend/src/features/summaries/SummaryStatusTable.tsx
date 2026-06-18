"use client";

import Link from "next/link";
import { useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { Member, Summary, SummaryJob } from "@/types";
import styles from "./SummaryStatusTable.module.css";

type Props = {
  projectId: string;
  members: Member[];
  jobs: SummaryJob[];
  summaries: Summary[];
  onGenerate: (login: string) => Promise<void>;
  onGenerateAll: () => Promise<void>;
};

type JobStatus = SummaryJob["status"] | "none";

function getStatusBadge(status: JobStatus) {
  switch (status) {
    case "none":
      return <Badge>未生成</Badge>;
    case "pending":
      return <Badge tone="ochre">待機中</Badge>;
    case "running":
      return <Badge tone="slate">生成中</Badge>;
    case "succeeded":
      return <Badge tone="green">完了</Badge>;
    case "failed":
      return <Badge tone="red">失敗</Badge>;
  }
}

function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className={styles.progressWrap} aria-label={`PR要約 ${done}/${total}`}>
      <div className={styles.progressBar}>
        <div className={styles.progressFill} style={{ width: `${pct}%` }} />
      </div>
      <span className={`num ${styles.progressLabel}`}>
        PR要約 {done}/{total}
      </span>
    </div>
  );
}

type RowProps = {
  projectId: string;
  member: Member;
  job: SummaryJob | undefined;
  summary: Summary | undefined;
  onGenerate: (login: string) => Promise<void>;
};

function MemberRow({ projectId, member, job, summary, onGenerate }: RowProps) {
  const [busy, setBusy] = useState(false);

  const status: JobStatus = job?.status ?? "none";
  const isActive = status === "pending" || status === "running";
  const hasGenerated = status === "succeeded" || summary != null;

  const handleClick = async () => {
    setBusy(true);
    try {
      await onGenerate(member.github_login);
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className={styles.row}>
      <td className={styles.memberCell}>
        <div className={styles.memberIdent}>
          <Avatar
            login={member.github_login}
            url={member.avatar_url}
            size={28}
          />
          <span className={`num ${styles.login}`}>{member.github_login}</span>
        </div>
      </td>

      <td className={styles.statusCell}>{getStatusBadge(status)}</td>

      <td className={styles.progressCell}>
        {status === "running" && (
          <ProgressBar done={job!.done_prs} total={job!.total_prs} />
        )}
      </td>

      <td className={styles.summaryCell}>
        {status === "failed" && job?.error && (
          <span className={styles.errorText}>{job.error}</span>
        )}
        {status === "succeeded" && job?.finished_at && (
          <span className={`num ${styles.finishedAt}`}>
            {new Date(job.finished_at).toLocaleString("ja-JP")}
          </span>
        )}
        {summary && (
          <p className={styles.excerpt}>
            {summary.content.slice(0, 100)}
            {summary.content.length > 100 ? "…" : ""}
          </p>
        )}
      </td>

      <td className={styles.actionCell}>
        <div className={styles.actionGroup}>
          <Link
            href={`/projects/${projectId}/members/${member.github_login}`}
            className={styles.prDetailLink}
          >
            PR別を見る
          </Link>
          <Button
            variant="secondary"
            size="s"
            onClick={handleClick}
            loading={busy || isActive}
            disabled={busy || isActive}
          >
            {hasGenerated ? "再生成" : "生成"}
          </Button>
        </div>
      </td>
    </tr>
  );
}

export function SummaryStatusTable({
  projectId,
  members,
  jobs,
  summaries,
  onGenerate,
  onGenerateAll,
}: Props) {
  const [generatingAll, setGeneratingAll] = useState(false);

  const handleGenerateAll = async () => {
    setGeneratingAll(true);
    try {
      await onGenerateAll();
    } finally {
      setGeneratingAll(false);
    }
  };

  const jobByLogin = new Map(jobs.map((j) => [j.github_login, j]));
  const summaryByLogin = new Map(summaries.map((s) => [s.github_login, s]));

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <Button
          variant="secondary"
          size="s"
          onClick={handleGenerateAll}
          loading={generatingAll}
        >
          全員分生成
        </Button>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.thMember}>メンバー</th>
              <th className={styles.thStatus}>状態</th>
              <th className={styles.thProgress}>進捗</th>
              <th className={styles.thSummary}>サマリー</th>
              <th className={styles.thAction}></th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <MemberRow
                key={m.github_login}
                projectId={projectId}
                member={m}
                job={jobByLogin.get(m.github_login)}
                summary={summaryByLogin.get(m.github_login)}
                onGenerate={onGenerate}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
