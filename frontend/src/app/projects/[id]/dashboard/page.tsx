import Link from "next/link";
import styles from "./page.module.css";
import { AppShell } from "@/components/ui/AppShell";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { TotalScoreBarChart } from "@/features/dashboard/TotalScoreBarChart";
import { CategoryPieChart } from "@/features/dashboard/CategoryPieChart";
import { mockProjects, mockScores } from "@/lib/mockData";

type Params = Promise<{ id: string }>;

export default async function DashboardPage({ params }: { params: Params }) {
  const { id } = await params;
  const project = mockProjects.find((p) => p.id === id) ?? mockProjects[0];
  const sorted = [...mockScores].sort((a, b) => b.total - a.total);

  return (
    <AppShell projectId={project.id}>
      <header className={styles.header}>
        <div>
          <div className={styles.crumb}>
            <Link href="/projects">プロジェクト</Link>
            <span>/</span>
            <span>{project.name}</span>
          </div>
          <h1 className={styles.title}>ダッシュボード</h1>
          <p className={styles.subtitle}>
            {project.repository} の貢献データ ・ <Badge tone="muted">全期間</Badge>{" "}
            <span className={styles.lastSync}>📡 5分前に同期</span>
          </p>
        </div>
        <button className={styles.refresh} type="button">
          ↻ 最新データを取得
        </button>
      </header>

      <section className={styles.chartGrid}>
        <Card title="メンバー別総合スコア">
          <p className={styles.cardLead}>
            メンバー名をクリックすると、貢献の詳細とAI生成サマリーが見られます。
          </p>
          <TotalScoreBarChart scores={sorted} projectId={project.id} />
        </Card>

        <Card title="カテゴリ別スコア内訳">
          <p className={styles.cardLead}>
            プロジェクト全体の活動が、どのカテゴリにどれくらい集中しているか。
          </p>
          <CategoryPieChart scores={sorted} />
        </Card>
      </section>
    </AppShell>
  );
}
