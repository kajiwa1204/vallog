"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/ui/AppShell";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useProject } from "@/hooks/useProject";
import { api, ApiError } from "@/lib/api";
import { WeightEditor } from "@/features/projects/WeightEditor";
import { SpLabelGuide } from "@/features/projects/SpLabelGuide";
import type { CategoryWeights, Invitation, Member, Project } from "@/types";
import styles from "./page.module.css";

export default function SettingsPage() {
  const { id } = useParams<{ id: string }>();
  const { project, setProject } = useProject(id);

  const [members, setMembers] = useState<Member[] | null>(null);
  const [membersError, setMembersError] = useState<string | null>(null);

  const [savingWeights, setSavingWeights] = useState(false);
  const [weightsMessage, setWeightsMessage] = useState<string | null>(null);

  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [issuing, setIssuing] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .get<Member[]>(`/projects/${id}/members`)
      .then((data) => {
        if (!cancelled) setMembers(data);
      })
      .catch((e) => {
        if (!cancelled)
          setMembersError(
            e instanceof ApiError ? e.message : "メンバーの取得に失敗しました",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const saveWeights = async (weights: CategoryWeights) => {
    setSavingWeights(true);
    setWeightsMessage(null);
    try {
      const updated = await api.patch<Project>(`/projects/${id}`, { weights });
      setProject(updated);
      setWeightsMessage("保存しました");
    } catch (e) {
      setWeightsMessage(
        e instanceof ApiError ? e.message : "保存に失敗しました",
      );
    } finally {
      setSavingWeights(false);
    }
  };

  const issueInvitation = async () => {
    setIssuing(true);
    setCopied(false);
    setInviteError(null);
    try {
      setInvitation(await api.post<Invitation>(`/projects/${id}/invitations`));
    } catch (e) {
      setInviteError(
        e instanceof ApiError ? e.message : "招待リンクの発行に失敗しました",
      );
    } finally {
      setIssuing(false);
    }
  };

  const copyInvitation = async () => {
    if (!invitation) return;
    try {
      await navigator.clipboard.writeText(invitation.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setInviteError(
        "コピーに失敗しました。リンクを選択して手動でコピーしてください。",
      );
    }
  };

  return (
    <AppShell projectId={id} projectName={project?.name}>
      <header className={styles.header}>
        <h1 className={styles.title}>プロジェクト設定</h1>
      </header>

      {!project ? (
        <Spinner />
      ) : (
        <div className={styles.stack}>
          <Card title="リポジトリ">
            <div className={styles.repoRow}>
              <div>
                <p className={styles.projectName}>{project.name}</p>
                <a
                  className={`num ${styles.repoLink}`}
                  href={`https://github.com/${project.repo_owner}/${project.repo_name}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  github.com/{project.repo_owner}/{project.repo_name} ↗
                </a>
              </div>
              <span className={`num ${styles.createdAt}`}>
                登録 {new Date(project.created_at).toLocaleDateString("ja-JP")}
              </span>
            </div>
          </Card>

          <Card
            title="メンバー"
            actions={
              <span className={styles.cardNote}>
                GitHubのコントリビューターを自動取得しています
              </span>
            }
          >
            {membersError ? (
              <p className={styles.error}>{membersError}</p>
            ) : members === null ? (
              <Spinner label="コントリビューターを取得中…" />
            ) : members.length === 0 ? (
              <p className={styles.muted}>
                まだコントリビューターがいません。
              </p>
            ) : (
              <ul className={styles.memberList}>
                {members.map((m) => (
                  <li key={m.github_login} className={styles.memberRow}>
                    <Avatar
                      login={m.github_login}
                      url={m.avatar_url}
                      size={30}
                    />
                    <span className={`num ${styles.memberLogin}`}>
                      {m.github_login}
                    </span>
                    {m.is_member ? (
                      <Badge tone="green">Vallog登録済み</Badge>
                    ) : (
                      <Badge>未登録</Badge>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card
            title="招待リンク"
            actions={
              <span className={styles.cardNote}>
                7日間有効・チームで使い回せます
              </span>
            }
          >
            <div className={styles.inviteWrap}>
              <p className={styles.muted}>
                メンバーがこのリンクからGitHubでログインすると、プロジェクトに参加して
                スコアを確認できるようになります。privateリポジトリの場合、アクセス権の
                ないアカウントは参加できません。
              </p>
              {invitation ? (
                <div className={styles.inviteRow}>
                  <code className={`num ${styles.inviteUrl}`}>
                    {invitation.url}
                  </code>
                  <Button size="s" variant="secondary" onClick={copyInvitation}>
                    {copied ? "コピーしました ✓" : "コピー"}
                  </Button>
                </div>
              ) : (
                <Button onClick={issueInvitation} loading={issuing}>
                  招待リンクを発行する
                </Button>
              )}
              {invitation && (
                <p className={`num ${styles.inviteExpiry}`}>
                  有効期限:{" "}
                  {new Date(invitation.expires_at).toLocaleString("ja-JP")}
                </p>
              )}
              {inviteError && <p className={styles.error}>{inviteError}</p>}
            </div>
          </Card>

          <Card title="評価カテゴリの重み">
            <WeightEditor
              weights={project.weights}
              saving={savingWeights}
              onSave={saveWeights}
            />
            {weightsMessage && (
              <p className={styles.saveMessage}>{weightsMessage}</p>
            )}
          </Card>

          <Card title="SPラベルの設定（タスク完了スピードの計測）">
            <SpLabelGuide />
          </Card>
        </div>
      )}
    </AppShell>
  );
}
