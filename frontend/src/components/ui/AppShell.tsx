"use client";

import { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { Avatar } from "./Avatar";
import { Spinner } from "./Spinner";
import styles from "./AppShell.module.css";

export function Wordmark({ inverse = false }: { inverse?: boolean }) {
  return (
    <span className={`${styles.wordmark} ${inverse ? styles.inverse : ""}`}>
      vallog<span className={styles.cursor}>▌</span>
    </span>
  );
}

type Props = {
  children: ReactNode;
  projectId?: string;
  projectName?: string;
};

const PROJECT_NAV = [
  { href: "dashboard", label: "ダッシュボード" },
  { href: "distribution", label: "分配シミュレーション" },
  { href: "settings", label: "プロジェクト設定" },
];

export function AppShell({ children, projectId, projectName }: Props) {
  const { status, user, logout } = useAuth();
  const pathname = usePathname();

  if (status === "loading") {
    return (
      <div className={styles.loading}>
        <Spinner />
      </div>
    );
  }
  if (status !== "authenticated") return null;

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <Link href="/projects" className={styles.brand}>
          <Wordmark inverse />
        </Link>

        {projectId && (
          <nav className={styles.nav} aria-label="プロジェクト">
            {projectName && (
              <div className={styles.projectName}>{projectName}</div>
            )}
            {PROJECT_NAV.map((item) => {
              const href = `/projects/${projectId}/${item.href}`;
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={item.href}
                  href={href}
                  className={`${styles.navItem} ${active ? styles.active : ""}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        )}

        <div className={styles.spacer} />

        <Link href="/projects" className={styles.navItem}>
          プロジェクト一覧
        </Link>

        <div className={styles.user}>
          <Avatar login={user.github_login} url={user.avatar_url} size={30} />
          <div className={styles.userInfo}>
            <span className={styles.userName}>{user.github_login}</span>
            <button className={styles.logout} onClick={logout}>
              ログアウト
            </button>
          </div>
        </div>
      </aside>

      <main className={styles.main}>
        <div className={styles.content}>{children}</div>
      </main>
    </div>
  );
}
