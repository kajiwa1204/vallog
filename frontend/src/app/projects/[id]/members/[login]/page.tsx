import Link from "next/link";
import { notFound } from "next/navigation";
import styles from "./page.module.css";
import { AppShell } from "@/components/ui/AppShell";
import { Card } from "@/components/ui/Card";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { ScoreBreakdown } from "@/features/members/ScoreBreakdown";
import { ContributionSummary } from "@/features/members/ContributionSummary";
import { mockProjects, mockScores, mockSummaries } from "@/lib/mockData";

type Params = Promise<{ id: string; login: string }>;

export default async function MemberPage({ params }: { params: Params }) {
  const { id, login } = await params;
  const project = mockProjects.find((p) => p.id === id) ?? mockProjects[0];
  const score = mockScores.find((s) => s.login === login);
  const summary = mockSummaries[login];
  if (!score || !summary) notFound();

  return (
    <AppShell projectId={project.id}>
      <header className={styles.header}>
        <div className={styles.crumb}>
          <Link href={`/projects/${project.id}/dashboard`}>ダッシュボード</Link>
          <span>/</span>
          <span>メンバー</span>
        </div>
        <div className={styles.profile}>
          <Avatar src={score.avatarUrl} alt={score.name} size={64} />
          <div className={styles.profileText}>
            <h1 className={styles.name}>{score.name}</h1>
            <a
              href={`https://github.com/${score.login}`}
              target="_blank"
              rel="noreferrer"
              className={styles.login}
            >
              @{score.login} ↗
            </a>
          </div>
          <div className={styles.totalBox}>
            <div className={styles.totalLabel}>総合スコア</div>
            <div className={styles.totalValue}>{score.total}</div>
            <div className={styles.totalUnit}>pts</div>
          </div>
        </div>
      </header>

      <section className={styles.layout}>
        <div className={styles.colMain}>
          <Card
            title="貢献サマリー"
            actions={<Button size="sm" variant="secondary">↻ 再生成</Button>}
          >
            <ContributionSummary summary={summary} repository={project.repository} />
          </Card>
        </div>
        <div className={styles.colSide}>
          <Card title="カテゴリ別スコア内訳">
            <ScoreBreakdown score={score} />
          </Card>
          <Card title="アクティビティ概要">
            <ul className={styles.activity}>
              <li>
                <span>マージ済みPR</span>
                <strong>{score.counts.prsMerged}</strong>
              </li>
              <li>
                <span>クローズIssue</span>
                <strong>{score.counts.issuesClosed}</strong>
              </li>
              <li>
                <span>レビュー</span>
                <strong>{score.counts.reviewsGiven}</strong>
              </li>
              <li>
                <span>平均TAT</span>
                <strong>{score.counts.avgTatHours}h</strong>
              </li>
              <li>
                <span>SP合計</span>
                <strong>{score.counts.spTotal}</strong>
              </li>
            </ul>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}
