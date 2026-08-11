"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { ActivityChart } from "@/features/members/ActivityChart";
import { MemberChangeLog } from "@/features/members/ChangeLog";
import { ContributionFacts } from "@/features/members/ContributionFacts";
import { MemberSwitcher } from "@/features/members/MemberSwitcher";
import { useMemberDetail } from "@/features/members/useMemberDetail";
import { useAuth } from "@/hooks/useAuth";
import { useProject } from "@/hooks/useProject";
import styles from "./page.module.css";

/**
 * メンバー詳細（画面5）。
 *
 * 主軸はそのメンバーの変化ログで、スコアはこの画面に出さない
 * （docs/scoring_design.md「Goodhart対策とスコアの事後開示」。開示は画面7）。
 *
 * 想定する主な用途は「他人の成績を見に行く」ことではなく、**自分の貢献が正しく
 * 記録されているかを検算する**こと（#13 で変化ログの絞り込みが自分を先頭に固定した
 * 結果、その役割がこの画面に寄った）。だから数字は必ず下の一覧から数え直せる値に
 * 限り、他のメンバーの数字とは並べない。
 *
 * 一方で人の切り替え自体は塞がない。無給の有志チームでは「誰が何をしているか」を
 * 互いに知れることが協調の前提になるため。
 */
export default function MemberDetailPage() {
  const { id, login } = useParams<{ id: string; login: string }>();

  // リダイレクトは AppShell 側の useAuth が担う。ここでは認証確定を待つことと、
  // 自分自身のページかどうかを見分けるためにログインを参照する
  const { status, user } = useAuth({ required: false });
  const authed = status === "authenticated";
  const me = user?.github_login ?? null;
  const isMe = me !== null && me === login;

  const { project } = useProject(id, authed);
  const {
    changelog,
    facts,
    weeks,
    countedEntries,
    truncated,
    members,
    membersError,
  } = useMemberDetail(id, login, authed);

  // 記録が1件も無いときに0が並んだ集計とバーの無いグラフを出しても読むものがない。
  // 「まだ記録がありません」は一覧の空表示が引き受ける。
  // 取得に失敗したときも出さない。一覧が消えている横に数字だけ残ると、数えて
  // 確かめられない数字を主張することになる（この画面が成り立たなくなる）
  const hasRecords = changelog.error === null && changelog.entries.length > 0;

  return (
    <AppShell projectId={id} projectName={project?.name}>
      <header className={styles.header}>
        <div className={styles.identity}>
          <Avatar login={login} size={40} />
          <div>
            <h1 className={styles.title}>
              <span className="num">{login}</span>
              {isMe && <span className={styles.mine}>あなた</span>}
            </h1>
            <div className={styles.links}>
              <Link className={styles.back} href={`/projects/${id}/dashboard`}>
                ← ダッシュボード
              </Link>
              <a
                className={`num ${styles.profile}`}
                href={`https://github.com/${encodeURIComponent(login)}`}
                target="_blank"
                rel="noreferrer"
              >
                GitHub ↗
              </a>
            </div>
          </div>
        </div>
        <Button
          variant="secondary"
          size="s"
          onClick={changelog.reload}
          loading={changelog.loading}
        >
          再読み込み
        </Button>
      </header>

      <p className={styles.intro}>
        {"GitHubに残っている記録をそのまま並べています。点数も順位も出しません（分配を話し合うときに画面7でまとめて開きます）。"}
      </p>

      <MemberSwitcher
        projectId={id}
        members={members}
        membersError={membersError}
        current={login}
        me={me}
      />

      {hasRecords && (
        <div className={styles.overview}>
          <ContributionFacts
            facts={facts}
            isMe={isMe}
            countedEntries={countedEntries}
            truncated={truncated}
          />
          <ActivityChart weeks={weeks} truncated={truncated} />
        </div>
      )}

      <MemberChangeLog
        login={login}
        isMe={isMe}
        entries={changelog.entries}
        loading={changelog.loading}
        error={changelog.error}
        hasMore={changelog.hasMore}
        onLoadMore={changelog.loadMore}
        onRetry={changelog.reload}
      />
    </AppShell>
  );
}
