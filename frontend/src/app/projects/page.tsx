import Link from "next/link";
import styles from "./page.module.css";
import { mockProjects } from "@/lib/mockData";
import { Badge } from "@/components/ui/Badge";
import { formatYen } from "@/lib/mockData";

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("ja-JP", { year: "numeric", month: "short", day: "numeric" });

export default function ProjectsPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <Link href="/" className={styles.brand}>
            <span className={styles.brandMark}>V</span>
            <span>Vallog</span>
          </Link>
        </div>
        <div className={styles.userArea}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://avatars.githubusercontent.com/u/82638006?v=4"
            alt="Kameda Masato"
            width={28}
            height={28}
            className={styles.userAvatar}
          />
          <span>@shou6439</span>
        </div>
      </header>

      <section className={styles.titleRow}>
        <div>
          <h1 className={styles.title}>プロジェクト</h1>
          <p className={styles.subtitle}>あなたが参加しているプロジェクトの一覧です。</p>
        </div>
        <button className={styles.createButton} type="button">
          ＋ 新規プロジェクト
        </button>
      </section>

      <ul className={styles.grid}>
        {mockProjects.map((project) => (
          <li key={project.id}>
            <Link href={`/projects/${project.id}/dashboard`} className={styles.card}>
              <div className={styles.cardHeader}>
                <h2 className={styles.cardTitle}>{project.name}</h2>
                <Badge tone="accent">アクティブ</Badge>
              </div>
              <p className={styles.cardDesc}>{project.description}</p>
              <div className={styles.cardMeta}>
                <span>🗂 {project.repository}</span>
                <span>👥 {project.memberCount} メンバー</span>
                <span>💰 {formatYen(project.totalReward)}</span>
                <span>🕒 {formatDate(project.updatedAt)}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
