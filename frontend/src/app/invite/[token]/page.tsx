"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { GitHubIcon } from "@/components/ui/GitHubIcon";
import { Spinner } from "@/components/ui/Spinner";
import { Wordmark } from "@/components/ui/AppShell";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { startGitHubLogin } from "@/lib/auth";
import { messageForError } from "@/lib/errorMessages";
import type { InvitationInfo, JoinResponse } from "@/types";
import styles from "./page.module.css";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  // 未ログインでもプレビューを表示するためリダイレクトはしない
  const { status } = useAuth({ required: false });

  const [invitation, setInvitation] = useState<InvitationInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [joinError, setJoinError] = useState<string | null>(null);
  const joinStarted = useRef(false);

  useEffect(() => {
    let cancelled = false;
    api
      .get<InvitationInfo>(`/invitations/${token}`)
      .then((data) => {
        if (!cancelled) setInvitation(data);
      })
      .catch((e) => {
        if (!cancelled)
          setError(
            messageForError(e, {
              codes: {
                INVITATION_NOT_FOUND: "この招待リンクは無効です。",
                INVITATION_EXPIRED:
                  "この招待リンクは有効期限が切れています。プロジェクトのメンバーに再発行を依頼してください。",
              },
              fallback: "招待リンクの読み込みに失敗しました。",
            }),
          );
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  // ログイン済みなら自動で参加してプロジェクトへ遷移する（画面1: 招待リンク経由の自動遷移）
  useEffect(() => {
    if (status !== "authenticated" || invitation === null) return;
    if (joinStarted.current) return;
    joinStarted.current = true;

    api
      .post<JoinResponse>(`/invitations/${token}/join`)
      .then((res) => {
        router.replace(`/projects/${res.project_id}/dashboard`);
      })
      .catch((e) => {
        joinStarted.current = false;
        setJoinError(
          messageForError(e, {
            codes: {
              REPO_ACCESS_DENIED:
                "このプロジェクトのリポジトリへのアクセス権がないため参加できません。",
              INVITATION_EXPIRED: "この招待リンクは有効期限が切れています。",
              INVITATION_NOT_FOUND: "この招待リンクは無効です。",
            },
            fallback: "プロジェクトへの参加に失敗しました。",
          }),
        );
      });
  }, [status, invitation, token, router]);

  const expiresAt = invitation
    ? new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium" }).format(
        new Date(invitation.expires_at),
      )
    : null;

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <Wordmark />
        </div>

        {error && (
          <>
            <p className={styles.error} role="alert">
              {error}
            </p>
            <Button
              variant="secondary"
              className={styles.action}
              onClick={() => router.push("/")}
            >
              トップへ戻る
            </Button>
          </>
        )}

        {!error && (invitation === null || status === "loading") && <Spinner />}

        {!error && invitation !== null && status !== "loading" && (
          <>
            <p className={styles.lead}>プロジェクトに招待されています</p>
            <h1 className={styles.projectName}>{invitation.project_name}</h1>
            <p className={`${styles.repo} num`}>
              {invitation.repo_owner}/{invitation.repo_name}
            </p>
            <p className={styles.meta}>
              <span className="num">{invitation.member_count}</span> members ・{" "}
              <span className="num">{expiresAt}</span> まで有効
            </p>

            {joinError && (
              <p className={styles.error} role="alert">
                {joinError}
              </p>
            )}

            {status === "authenticated" && !joinError && (
              <div className={styles.joining}>
                <Spinner />
                <p className={styles.joiningText}>プロジェクトに参加しています…</p>
              </div>
            )}

            {status === "unauthenticated" && (
              <Button
                variant="primary"
                className={styles.action}
                onClick={() => startGitHubLogin(`/invite/${token}`)}
              >
                <GitHubIcon />
                GitHubでログインして参加
              </Button>
            )}
          </>
        )}
      </div>
    </main>
  );
}
