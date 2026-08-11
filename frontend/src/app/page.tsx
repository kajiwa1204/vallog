"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { GitHubIcon } from "@/components/ui/GitHubIcon";
import { Spinner } from "@/components/ui/Spinner";
import { Wordmark } from "@/components/ui/AppShell";
import { useAuth } from "@/hooks/useAuth";
import { startGitHubLogin } from "@/lib/auth";
import { REPO_SCOPE_NOTICE } from "@/lib/githubAccess";
import styles from "./page.module.css";

const ERROR_MESSAGES: Record<string, string> = {
  auth_denied: "GitHub認証がキャンセルされました。もう一度お試しください。",
  auth_failed: "ログインに失敗しました。もう一度お試しください。",
  auth_state_mismatch:
    "認証リクエストを検証できませんでした。お手数ですが、この画面からもう一度ログインしてください。",
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
      <div className={styles.loadingWrap}>
        <Spinner />
      </div>
    );
  }

  const error = searchParams.get("error");
  const errorMessage = error
    ? (ERROR_MESSAGES[error] ?? ERROR_MESSAGES.auth_failed)
    : null;

  return (
    <div className={styles.root}>
      {/* Left brand panel */}
      <div className={styles.brand}>
        <div className={styles.brandTop}>
          <Wordmark inverse />
        </div>

        <div className={styles.brandCenter}>
          <h1 className={styles.copy}>貢献を、記録する。</h1>
          <p className={styles.desc}>
            チーム開発の貢献を客観データで可視化し、正しく報いるためのインフラ。スコアの根拠はすべてGitHubの実データに直リンクします。
          </p>

          {/* Contribution bars */}
          <div className={styles.bars} aria-hidden>
            <div className={`${styles.bar} ${styles.barActivity}`} />
            <div className={`${styles.bar} ${styles.barSpeed}`} />
            <div className={`${styles.bar} ${styles.barQuality}`} />
          </div>
        </div>

        <div className={styles.brandBottom}>
          <span className={`${styles.value} num`}>透明性</span>
          <span className={styles.valueSep}>/</span>
          <span className={`${styles.value} num`}>客観性</span>
          <span className={styles.valueSep}>/</span>
          <span className={`${styles.value} num`}>チームの自律</span>
        </div>
      </div>

      {/* Right login panel */}
      <div className={styles.login}>
        <div className={styles.loginCard}>
          <h2 className={styles.loginTitle}>Vallogにログイン</h2>

          {errorMessage && (
            <p className={styles.error} role="alert">
              {errorMessage}
            </p>
          )}

          <button
            type="button"
            className={styles.githubButton}
            onClick={() => startGitHubLogin()}
          >
            <GitHubIcon size={20} />
            GitHubでログイン
          </button>

          <div className={styles.noteGroup}>
            <p className={styles.note}>
              ログインすることで、GitHubのリポジトリ情報（privateを含む）の読み取りを許可します。
            </p>
            <p className={styles.noteDetail}>{REPO_SCOPE_NOTICE}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className={styles.loadingWrap}>
          <Spinner />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
