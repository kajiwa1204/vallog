import Link from "next/link";
import styles from "./page.module.css";
import { AppShell } from "@/components/ui/AppShell";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Avatar } from "@/components/ui/Avatar";
import { mockMembers, mockProjects } from "@/lib/mockData";

type Params = Promise<{ id: string }>;

export default async function SettingsPage({ params }: { params: Params }) {
  const { id } = await params;
  const project = mockProjects.find((p) => p.id === id) ?? mockProjects[0];

  return (
    <AppShell projectId={project.id}>
      <header className={styles.header}>
        <div className={styles.crumb}>
          <Link href={`/projects/${project.id}/dashboard`}>ダッシュボード</Link>
          <span>/</span>
          <span>プロジェクト設定</span>
        </div>
        <h1 className={styles.title}>プロジェクト設定</h1>
      </header>

      <div className={styles.grid}>
        <Card title="基本情報" actions={<Button size="sm" variant="secondary">編集</Button>}>
          <dl className={styles.dl}>
            <div className={styles.dlRow}>
              <dt>プロジェクト名</dt>
              <dd>{project.name}</dd>
            </div>
            <div className={styles.dlRow}>
              <dt>説明</dt>
              <dd>{project.description}</dd>
            </div>
            <div className={styles.dlRow}>
              <dt>連携リポジトリ</dt>
              <dd>
                <a href={`https://github.com/${project.repository}`} target="_blank" rel="noreferrer">
                  {project.repository} ↗
                </a>
              </dd>
            </div>
            <div className={styles.dlRow}>
              <dt>総報酬額</dt>
              <dd>
                ¥{project.totalReward.toLocaleString("ja-JP")}{" "}
                <Badge tone="muted">分配対象</Badge>
              </dd>
            </div>
          </dl>
        </Card>

        <Card
          title="メンバー"
          actions={<Button size="sm">＋ 招待リンクを発行</Button>}
        >
          <ul className={styles.memberList}>
            {mockMembers.map((m) => (
              <li key={m.login} className={styles.memberRow}>
                <Avatar src={m.avatarUrl} alt={m.name} size={32} />
                <div className={styles.memberId}>
                  <div className={styles.memberName}>{m.name}</div>
                  <div className={styles.memberLogin}>@{m.login}</div>
                </div>
                {m.role === "owner" ? (
                  <Badge tone="accent">Owner</Badge>
                ) : (
                  <Badge tone="muted">Member</Badge>
                )}
              </li>
            ))}
          </ul>
        </Card>

        <Card title="データ同期">
          <p className={styles.note}>
            GitHub APIから Issue / PR / レビュー / SPラベル を取得します。
            最新データは画面リロード時に再取得されます。
          </p>
          <div className={styles.syncRow}>
            <div>
              <div className={styles.syncLabel}>最終同期</div>
              <div className={styles.syncValue}>5分前</div>
            </div>
            <Button variant="secondary">↻ いま同期する</Button>
          </div>
        </Card>

        <Card title="デンジャーゾーン">
          <div className={styles.dangerRow}>
            <div>
              <div className={styles.dangerTitle}>プロジェクトを削除</div>
              <div className={styles.dangerHint}>
                スコア・分配履歴を含むすべてのデータが削除されます。元に戻せません。
              </div>
            </div>
            <Button variant="secondary" className={styles.dangerButton}>削除する</Button>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
