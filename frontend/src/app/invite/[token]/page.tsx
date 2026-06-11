"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { Wordmark } from "@/components/ui/AppShell";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { api, ApiError } from "@/lib/api";
import type { InvitationInfo } from "@/types";
import styles from "./page.module.css";

export default function InvitePage() {
  const params = useParams();
  const token = params.token as string;
  const router = useRouter();
  const { status } = useAuth({ required: false });

  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [infoError, setInfoError] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<InvitationInfo>(`/invitations/${token}`)
      .then((data) => setInfo(data))
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "招待情報を取得できませんでした";
        setInfoError(msg);
      });
  }, [token]);

  async function handleJoin() {
    setJoining(true);
    setJoinError(null);
    try {
      await api.post(`/invitations/${token}/join`);
      if (info) {
        router.push(`/projects/${info.project_id}/dashboard`);
      }
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : "参加に失敗しました";
      setJoinError(msg);
      setJoining(false);
    }
  }

  function formatExpiry(dateStr: string) {
    try {
      return new Date(dateStr).toLocaleDateString("ja-JP", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
    } catch {
      return dateStr;
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.card}>
        <div className={styles.wordmark}>
          <Wordmark />
        </div>

        {status === "loading" && (
          <div className={styles.center}>
            <Spinner />
          </div>
        )}

        {status !== "loading" && infoError && (
          <p className={styles.invalid}>
            この招待リンクは無効か、有効期限が切れています
          </p>
        )}

        {status !== "loading" && !infoError && !info && (
          <div className={styles.center}>
            <Spinner label="招待情報を取得中…" />
          </div>
        )}

        {status !== "loading" && !infoError && info && (
          <>
            <p className={styles.lead}>プロジェクトへの招待が届いています</p>

            <div className={styles.projectInfo}>
              <div className={styles.projectName}>{info.project_name}</div>
              <div className={`${styles.repo} num`}>
                {info.repo_owner}/{info.repo_name}
              </div>
              <div className={styles.meta}>
                <span className={`${styles.metaItem} num`}>
                  {info.member_count} members
                </span>
                <span className={styles.metaSep}>·</span>
                <span className={styles.metaLabel}>有効期限</span>
                <span className={`${styles.metaItem} num`}>
                  {formatExpiry(info.expires_at)}
                </span>
              </div>
            </div>

            {joinError && (
              <p className={styles.error}>{joinError}</p>
            )}

            {status === "unauthenticated" && (
              <a
                href={`/api/auth/github/login?invite=${token}`}
                className={styles.githubButton}
              >
                <svg
                  className={styles.octicon}
                  viewBox="0 0 16 16"
                  width="20"
                  height="20"
                  aria-hidden="true"
                  fill="currentColor"
                >
                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                </svg>
                GitHubでログインして参加
              </a>
            )}

            {status === "authenticated" && (
              <Button
                variant="primary"
                onClick={handleJoin}
                loading={joining}
                disabled={joining}
              >
                このプロジェクトに参加する
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
