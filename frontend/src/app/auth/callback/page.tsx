"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Spinner } from "@/components/ui/Spinner";
import { refreshSession } from "@/lib/api";
import { consumeReturnTo } from "@/lib/auth";
import styles from "./page.module.css";

// バックエンドの /auth/github/callback が refresh token を Cookie にセットして
// ここへリダイレクトする。Cookie からセッションを確立してアプリへ遷移する。
export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const session = await refreshSession();
      if (cancelled) return;
      if (session) {
        router.replace(consumeReturnTo() ?? "/projects");
      } else {
        router.replace("/?error=auth_failed");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <main className={styles.page}>
      <Spinner />
      <p className={styles.text}>ログインしています…</p>
    </main>
  );
}
