"use client";

import { Suspense } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { Wordmark } from "@/components/ui/AppShell";
import { Spinner } from "@/components/ui/Spinner";
import { SetupWizard } from "@/features/setup/SetupWizard";
import { API_BASE_URL } from "@/constants";
import type { SetupStatus } from "@/features/setup/types";
import styles from "./page.module.css";

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const invite = searchParams.get("invite");
  const { status } = useAuth({ required: false });

  const [setupPhase, setSetupPhase] = useState<"loading" | "configured" | "wizard">("loading");
  const [callbackUrl, setCallbackUrl] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/setup/status`);
        if (!res.ok) {
          // バックエンドが応答しない場合は設定済みとみなしてログイン画面を表示
          if (!cancelled) setSetupPhase("configured");
          return;
        }
        const data: SetupStatus = await res.json();
        if (cancelled) return;
        if (data.configured) {
          setSetupPhase("configured");
        } else {
          setCallbackUrl(data.callback_url);
          setSetupPhase("wizard");
        }
      } catch {
        if (!cancelled) setSetupPhase("configured");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (status === "authenticated") {
      if (invite) {
        router.replace(`/invite/${invite}`);
      } else {
        router.replace("/projects");
      }
    }
  }, [status, invite, router]);

  if (status === "loading" || setupPhase === "loading") {
    return (
      <div className={styles.loadingWrap}>
        <Spinner />
      </div>
    );
  }

  // ウィザードモード: OAuth未設定の場合は右パネルにウィザードを表示
  if (setupPhase === "wizard") {
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

        {/* Right setup panel */}
        <div className={styles.login}>
          <SetupWizard
            callbackUrl={callbackUrl}
            onComplete={() => setSetupPhase("configured")}
          />
        </div>
      </div>
    );
  }

  const loginUrl = invite
    ? `/api/auth/github/login?invite=${invite}`
    : `/api/auth/github/login`;

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

          <a href={loginUrl} className={styles.githubButton}>
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
            GitHubでログイン
          </a>

          <p className={styles.note}>
            ログインすることで、GitHubの公開・所属リポジトリ情報の読み取りを許可します
          </p>
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
