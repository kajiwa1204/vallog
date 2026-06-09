"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode } from "react";
import styles from "./AppShell.module.css";
import { mockProjects } from "@/lib/mockData";

type Props = {
  projectId: string;
  children: ReactNode;
};

const navItems = (projectId: string) => [
  { href: `/projects/${projectId}/dashboard`, label: "ダッシュボード", emoji: "📊" },
  { href: `/projects/${projectId}/distribution`, label: "分配シミュレーション", emoji: "💰" },
  { href: `/projects/${projectId}/settings`, label: "プロジェクト設定", emoji: "⚙️" },
];

export function AppShell({ projectId, children }: Props) {
  const pathname = usePathname();
  const project = mockProjects.find((p) => p.id === projectId) ?? mockProjects[0];

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <Link href="/projects" className={styles.brand}>
          <span className={styles.brandMark}>V</span>
          <span className={styles.brandText}>Vallog</span>
        </Link>
        <div className={styles.projectSwitcher}>
          <div className={styles.projectLabel}>現在のプロジェクト</div>
          <Link href={`/projects/${project.id}/dashboard`} className={styles.projectName}>
            {project.name}
          </Link>
          <Link href="/projects" className={styles.projectChange}>
            プロジェクト変更
          </Link>
        </div>
        <nav className={styles.nav}>
          {navItems(projectId).map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[styles.navItem, active ? styles.navItemActive : ""].join(" ")}
              >
                <span className={styles.navEmoji}>{item.emoji}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className={styles.sidebarFooter}>
          <div className={styles.repoLabel}>連携リポジトリ</div>
          <a
            href={`https://github.com/${project.repository}`}
            target="_blank"
            rel="noreferrer"
            className={styles.repoLink}
          >
            {project.repository}
          </a>
        </div>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
