"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useProject } from "@/hooks/useProject";
import { useMemberDetail } from "@/features/members/useMemberDetail";
import { ScoreBreakdown } from "@/features/members/ScoreBreakdown";
import { ActivityTimeline } from "@/features/members/ActivityTimeline";
import { ContributionSummary } from "@/features/members/ContributionSummary";
import { PRSummarySection } from "@/features/members/PRSummarySection";
import { RecentItems } from "@/features/members/RecentItems";
import styles from "./page.module.css";

export default function MemberDetailPage() {
  const { id, login } = useParams<{ id: string; login: string }>();
  const { project } = useProject(id);
  const {
    detail,
    loading,
    error,
    generating,
    jobProgress,
    summaryError,
    generateSummary,
  } = useMemberDetail(id, login);

  return (
    <AppShell projectId={id} projectName={project?.name}>
      <nav className={styles.breadcrumb}>
        <Link href={`/projects/${id}/dashboard`} className={styles.crumbLink}>
          ダッシュボード
        </Link>
        <span className={styles.crumbSep}>/</span>
        <span className="num">{login}</span>
      </nav>

      {loading ? (
        <Spinner />
      ) : error || !detail ? (
        <Card>
          <p className={styles.error}>{error ?? "読み込みに失敗しました"}</p>
        </Card>
      ) : (
        <>
          <header className={styles.header}>
            <div className={styles.identity}>
              <Avatar
                login={login}
                url={detail.score.avatar_url}
                size={52}
              />
              <div>
                <h1 className={`num ${styles.login}`}>{login}</h1>
                <div className={styles.meta}>
                  {detail.score.is_registered ? (
                    <Badge tone="green">Vallog登録済み</Badge>
                  ) : (
                    <Badge>未登録</Badge>
                  )}
                  <a
                    className={styles.ghLink}
                    href={`https://github.com/${login}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    GitHubプロフィール ↗
                  </a>
                </div>
              </div>
            </div>
            <div className={styles.totalScore}>
              <span className={`num ${styles.totalValue}`}>
                {(detail.score.total * 100).toFixed(1)}
              </span>
              <span className={styles.totalLabel}>総合スコア</span>
            </div>
          </header>

          <div className={styles.stack}>
            <Card title="貢献サマリー" padding="m">
              <ContributionSummary
                summary={detail.summary}
                generating={generating}
                jobProgress={jobProgress}
                error={summaryError}
                onGenerate={generateSummary}
              />
            </Card>

            <PRSummarySection projectId={id} login={login} />

            <section>
              <h2 className={styles.sectionTitle}>カテゴリ別スコア内訳</h2>
              <ScoreBreakdown detail={detail} />
            </section>

            <Card title="活動の推移（直近12週）">
              <ActivityTimeline timeline={detail.timeline} />
            </Card>

            <Card title="スコアの根拠データ">
              <div className={styles.itemsGrid}>
                <RecentItems
                  title="Pull Request"
                  items={detail.recent_prs}
                  emptyText="PRはまだありません"
                />
                <RecentItems
                  title="Issue"
                  items={detail.recent_issues}
                  emptyText="Issueはまだありません"
                />
                <RecentItems
                  title="レビュー"
                  items={detail.recent_reviews}
                  emptyText="レビューはまだありません"
                />
              </div>
            </Card>
          </div>
        </>
      )}
    </AppShell>
  );
}
