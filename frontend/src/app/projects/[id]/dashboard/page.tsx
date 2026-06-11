"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useProject } from "@/hooks/useProject";
import { useDashboard } from "@/features/dashboard/useDashboard";
import { ScoreBarChart } from "@/features/dashboard/ScoreBarChart";
import { CategoryDonut } from "@/features/dashboard/CategoryDonut";
import styles from "./page.module.css";

export default function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  const { project } = useProject(id);
  const { scores, loading, refreshing, error, refresh } = useDashboard(id);
  const [selected, setSelected] = useState<string | null>(null);

  const members = scores?.members ?? [];
  const selectedMember =
    members.find((m) => m.github_login === selected) ?? members[0] ?? null;

  return (
    <AppShell projectId={id} projectName={project?.name}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>ダッシュボード</h1>
          {project && (
            <a
              className={`num ${styles.repo}`}
              href={`https://github.com/${project.repo_owner}/${project.repo_name}`}
              target="_blank"
              rel="noreferrer"
            >
              {project.repo_owner}/{project.repo_name} ↗
            </a>
          )}
        </div>
        <div className={styles.headerActions}>
          {scores?.synced_at && (
            <span className={`num ${styles.synced}`}>
              同期 {new Date(scores.synced_at).toLocaleString("ja-JP")}
            </span>
          )}
          <Button
            variant="secondary"
            size="s"
            onClick={refresh}
            loading={refreshing}
          >
            GitHubと同期
          </Button>
        </div>
      </header>

      {loading ? (
        <Spinner label="GitHubのデータからスコアを計算しています…" />
      ) : error ? (
        <Card>
          <p className={styles.error}>{error}</p>
        </Card>
      ) : members.length === 0 ? (
        <Card>
          <div className={styles.empty}>
            <p>まだスコアの対象となる活動がありません。</p>
            <p className={styles.emptyHint}>
              PRやIssueが作成されると、ここに貢献スコアが表示されます。
            </p>
          </div>
        </Card>
      ) : (
        <div className={styles.grid}>
          <Card
            title="メンバー別総合スコア"
            actions={
              <span className={styles.cardNote}>クリックで内訳を表示</span>
            }
            className={styles.barCard}
          >
            <ScoreBarChart
              members={members}
              weights={scores!.weights}
              selected={selectedMember?.github_login ?? null}
              onSelect={(login) => setSelected(login)}
            />
          </Card>

          <Card
            title={
              selectedMember
                ? `${selectedMember.github_login} の内訳`
                : "カテゴリ別内訳"
            }
            actions={
              selectedMember && (
                <Link
                  className={styles.detailLink}
                  href={`/projects/${id}/members/${selectedMember.github_login}`}
                >
                  詳細を見る →
                </Link>
              )
            }
            className={styles.donutCard}
          >
            {selectedMember && (
              <CategoryDonut member={selectedMember} weights={scores!.weights} />
            )}
          </Card>
        </div>
      )}
    </AppShell>
  );
}
