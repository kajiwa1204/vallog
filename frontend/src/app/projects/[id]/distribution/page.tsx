import Link from "next/link";
import styles from "./page.module.css";
import { AppShell } from "@/components/ui/AppShell";
import { DistributionWorkbench } from "@/features/distribution/DistributionWorkbench";
import { ContributionContext } from "@/features/distribution/ContributionContext";
import { mockProjects } from "@/lib/mockData";

type Params = Promise<{ id: string }>;

export default async function DistributionPage({ params }: { params: Params }) {
  const { id } = await params;
  const project = mockProjects.find((p) => p.id === id) ?? mockProjects[0];
  return (
    <AppShell projectId={project.id}>
      <header className={styles.header}>
        <div className={styles.crumb}>
          <Link href={`/projects/${project.id}/dashboard`}>ダッシュボード</Link>
          <span>/</span>
          <span>分配シミュレーション</span>
        </div>
        <h1 className={styles.title}>分配シミュレーション</h1>
        <p className={styles.subtitle}>
          重みをカスタマイズして分配額の試算を行い、複数案を保存して比較できます。
          AIは判断には関与しません。最終的な分配の決定はチームで行ってください。
        </p>
      </header>
      <section className={styles.contextSection}>
        <ContributionContext projectId={project.id} />
      </section>
      <DistributionWorkbench />
    </AppShell>
  );
}
