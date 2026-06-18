"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useProject } from "@/hooks/useProject";
import { useMembers } from "@/features/summaries/useMembers";
import { useSummaryJobs } from "@/features/summaries/useSummaryJobs";
import { SummaryStatusTable } from "@/features/summaries/SummaryStatusTable";
import styles from "./page.module.css";

export default function SummariesPage() {
  const { id } = useParams<{ id: string }>();
  const { project } = useProject(id);
  const { members, loading: membersLoading, error: membersError } = useMembers(id);
  const logins = members.map((m) => m.github_login);
  const {
    jobs,
    summaries,
    loading: jobsLoading,
    error: jobsError,
    generateOne,
    generateAll,
  } = useSummaryJobs(id, logins);

  const loading = membersLoading || jobsLoading;
  const error = membersError ?? jobsError;

  return (
    <AppShell projectId={id} projectName={project?.name}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>貢献サマリー生成状況</h1>
          <p className={styles.subtitle}>
            各メンバーのPR・コミット内容からサマリーを生成します。
            生成には数分かかることがあります。
          </p>
        </div>
      </header>

      {loading ? (
        <Spinner />
      ) : error ? (
        <Card>
          <p className={styles.error}>{error}</p>
        </Card>
      ) : members.length === 0 ? (
        <Card>
          <p className={styles.empty}>
            まだメンバーがいません。GitHubと同期するとコントリビューターが表示されます。
          </p>
        </Card>
      ) : (
        <Card title="メンバー別サマリー" padding="none">
          <SummaryStatusTable
            projectId={id}
            members={members}
            jobs={jobs}
            summaries={summaries}
            onGenerate={generateOne}
            onGenerateAll={generateAll}
          />
        </Card>
      )}
    </AppShell>
  );
}
