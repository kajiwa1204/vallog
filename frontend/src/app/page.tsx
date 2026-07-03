"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { GitHubIcon } from "@/components/ui/GitHubIcon";
import { Spinner } from "@/components/ui/Spinner";
import { Wordmark } from "@/components/ui/AppShell";
import { useAuth } from "@/hooks/useAuth";
import { startGitHubLogin } from "@/lib/auth";
import styles from "./page.module.css";

const ERROR_MESSAGES: Record<string, string> = {
  auth_denied: "GitHub認証がキャンセルされました。もう一度お試しください。",
  auth_failed: "ログインに失敗しました。もう一度お試しください。",
};

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // 未ログインでもこの画面に留まる（リダイレクトはしない）
  const { status } = useAuth({ required: false });

  useEffect(() => {
    if (status === "authenticated") router.replace("/projects");
  }, [status, router]);

  // セッション確認中・ログイン済み（遷移待ち）はスピナーのみ表示
  if (status !== "unauthenticated") {
    return (
      <main className={styles.page}>
        <Spinner />
      </main>
    );
  }

  const error = searchParams.get("error");
  const errorMessage = error
    ? (ERROR_MESSAGES[error] ?? ERROR_MESSAGES.auth_failed)
    : null;

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <Wordmark />
        </div>
        <p className={styles.tagline}>貢献を、記録する</p>
        <p className={styles.description}>
          チーム開発の貢献を客観データで可視化し、正しく報いるためのインフラ
        </p>

        {errorMessage && (
          <p className={styles.error} role="alert">
            {errorMessage}
          </p>
        )}

        <Button
          variant="primary"
          className={styles.loginButton}
          onClick={() => startGitHubLogin()}
        >
          <GitHubIcon />
          GitHubでログイン
        </Button>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className={styles.page}>
          <Spinner />
        </main>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
