"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { SummaryList } from "@/features/summaries/SummaryList";
import { useSummaries } from "@/features/summaries/useSummaries";
import { useAuth } from "@/hooks/useAuth";
import { useProject } from "@/hooks/useProject";
import styles from "./page.module.css";

export default function SummariesPage() {
  const { id } = useParams<{ id: string }>();
  const { status } = useAuth({ required: false });
  const authed = status === "authenticated";
  const { project } = useProject(id, authed);
  const {
    members,
    summariesByLogin,
    jobsByLogin,
    loading,
    error,
    startingLogins,
    generatingAll,
    unchangedLogins,
    generate,
    generateAll,
    reload,
  } = useSummaries(id, authed);

  const activeJobs = [...jobsByLogin.values()].filter(
    (job) => job.status === "pending" || job.status === "running",
  ).length;
  return (
    <AppShell projectId={id} projectName={project?.name}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>貢献サマリー</h1>
          <p className={styles.subtitle}>
            GitHubに残った活動をAIが文章にまとめます。主張の #番号から一次情報を確認できます。
          </p>
        </div>
        <Button
          onClick={generateAll}
          loading={generatingAll}
          disabled={
            loading ||
            members.length === 0 ||
            activeJobs > 0 ||
            startingLogins.length > 0
          }
        >
          全員分を生成
        </Button>
      </header>

      <p className={styles.notice}>
        サマリー生成は手動で開始します。AIが停止・失敗しても、ダッシュボードの変化ログやスコア計算には影響しません。
      </p>

      <Card title="メンバー別サマリー">
        {error && <ErrorState message={error} onRetry={reload} retrying={loading} />}
        {!error && loading ? (
          <Spinner label="貢献サマリーを読み込んでいます…" />
        ) : (
          <SummaryList
            projectId={id}
            repoOwner={project?.repo_owner}
            repoName={project?.repo_name}
            members={members}
            summariesByLogin={summariesByLogin}
            jobsByLogin={jobsByLogin}
            startingLogins={startingLogins}
            generatingAll={generatingAll}
            unchangedLogins={unchangedLogins}
            generationDisabled={loading}
            onGenerate={generate}
          />
        )}
      </Card>
    </AppShell>
  );
}
