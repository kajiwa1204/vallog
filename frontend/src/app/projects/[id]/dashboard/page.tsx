"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { NeedsAttention } from "@/features/dashboard/NeedsAttention";
import { RecentlyDone } from "@/features/dashboard/RecentlyDone";
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
 * 代わりに「チームがいま何を動かしているか」を3つのパネルで示す。
 *
 * レビュー本数の集計（旧 ReviewFlow）は置かない。変化ログが1件ずつに脱集約している
 * 情報を画面が再集約して序列に戻すことになり、「数字の降格」に反するため。
 */
export default function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  // リダイレクトは AppShell 側の useAuth が担う。ここでは認証確定を待つことと、
  // 「自分」の行を見分けるためにログインを参照する
  const { status, user } = useAuth({ required: false });
  const authed = status === "authenticated";
  const me = user?.github_login ?? null;

  const { project } = useProject(id, authed);
  const {
    panels,
    panelsError,
    panelsLoading,
    changelog,
    newSince,
    roster,
    selectedMember,
    selectMember,
    syncing,
    reload,
  } = useDashboard(id, authed);

  // 同期は終わっているのにデータが1件も無い＝活動がまだ無いチーム。初めて開いた人には
  // 空のパネルが並ぶだけになるので、この画面が何をする場所なのかを言う
  const isFresh =
    panels !== null &&
    !syncing &&
    changelog.entries.length === 0 &&
    !changelog.loading;

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

      {isFresh && (
        <div className={styles.intro}>
          <p className={styles.introLead}>
            この画面は、チームがいま何を動かしているかをGitHubのPR・Issue・レビューから映します。
          </p>
          <p className={styles.introBody}>
            リポジトリで最初のPRやIssueが動くと、止まっているもの・片づいたもの・活動のリズムがここに出ます。
            記録された変化は、そのまま分配を話し合うときの材料になります。順位や点数は出しません。
          </p>
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
            {/* 上段に「止まっているもの」と「片づいたもの」を左右に並べる。互いの
                裏返しなので、横に置くと詰まりと流れが一目で比べられる。下段は
                どちらも集計（リズムと領域）で揃える */}
            <div className={styles.column}>
              <NeedsAttention attention={panels.attention} me={me} />
              <TeamPulse
                days={panels.pulse}
                previousTotal={panels.pulse_previous_total}
              />
            </div>
            <div className={styles.column}>
              <RecentlyDone items={panels.recently_done} />
              <Themes themes={panels.themes} />
            </div>
          </div>
        )
      )}

      <div className={styles.changelog}>
        <TeamChangeLog
          entries={changelog.entries}
          newSince={newSince}
          roster={roster}
          me={me}
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
