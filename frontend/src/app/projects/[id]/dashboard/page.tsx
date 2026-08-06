"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { NeedsAttention } from "@/features/dashboard/NeedsAttention";
import { ReviewFlow } from "@/features/dashboard/ReviewFlow";
import { TeamChangeLog } from "@/features/dashboard/TeamChangeLog";
import { TeamPulse } from "@/features/dashboard/TeamPulse";
import { Themes } from "@/features/dashboard/Themes";
import { useDashboard } from "@/features/dashboard/useDashboard";
import { useAuth } from "@/hooks/useAuth";
import { useProject } from "@/hooks/useProject";
import styles from "./page.module.css";

/**
 * ダッシュボード（画面4）。
 *
 * 主役はチームの変化ログで、スコアはこの画面に出さない
 * （docs/scoring_design.md「Goodhart対策とスコアの事後開示」。開示は画面7）。
 * 代わりに「チームがいま何を動かしているか」を4つのパネルで示す。
 */
export default function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  // リダイレクトは AppShell 側の useAuth が担う。ここでは認証確定を待つためだけに参照する
  const { status } = useAuth({ required: false });
  const authed = status === "authenticated";

  const { project } = useProject(id, authed);
  const {
    panels,
    panelsError,
    panelsLoading,
    changelog,
    roster,
    selectedMember,
    selectMember,
    syncing,
    reload,
  } = useDashboard(id, authed);

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
          <span className={`num ${styles.synced}`}>
            {panels?.synced_at
              ? `同期 ${new Date(panels.synced_at).toLocaleString("ja-JP")}`
              : "未同期"}
          </span>
          <Button
            variant="secondary"
            size="s"
            onClick={reload}
            loading={panelsLoading || changelog.loading}
          >
            再読み込み
          </Button>
        </div>
      </header>

      {syncing && (
        <div className={styles.banner}>
          GitHubからの初回同期中です。完了までしばらくかかります。「再読み込み」で最新の状態を取得できます。
        </div>
      )}

      {panelsError ? (
        <Card>
          <p className={styles.error}>{panelsError}</p>
        </Card>
      ) : panelsLoading && panels === null ? (
        <Card>
          <Spinner label="チームの状況を読み込んでいます…" />
        </Card>
      ) : (
        panels && (
          <div className={styles.panels}>
            <div className={styles.column}>
              <NeedsAttention attention={panels.attention} />
              <ReviewFlow edges={panels.collaboration} />
            </div>
            <div className={styles.column}>
              <TeamPulse days={panels.pulse} />
              <Themes themes={panels.themes} />
            </div>
          </div>
        )
      )}

      <div className={styles.changelog}>
        <TeamChangeLog
          projectId={id}
          entries={changelog.entries}
          roster={roster}
          selected={selectedMember}
          onSelect={selectMember}
          loading={changelog.loading}
          error={changelog.error}
          hasMore={changelog.hasMore}
          onLoadMore={changelog.loadMore}
          syncing={syncing}
        />
      </div>
    </AppShell>
  );
}
