"use client";

import { useState } from "react";
import { AppShell } from "@/components/ui/AppShell";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { useProjects } from "@/features/projects/useProjects";
import { ProjectCard } from "@/features/projects/ProjectCard";
import { NewProjectModal } from "@/features/projects/NewProjectModal";
import styles from "./page.module.css";

export default function ProjectsPage() {
  const { projects, loading, error } = useProjects();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <AppShell>
      <div className={styles.page}>
        <div className={styles.header}>
          <h1 className={styles.title}>プロジェクト</h1>
          <Button variant="primary" onClick={() => setModalOpen(true)}>
            リポジトリを登録
          </Button>
        </div>

        {loading && (
          <div className={styles.center}>
            <Spinner />
          </div>
        )}

        {error && !loading && (
          <p className={styles.error}>{error}</p>
        )}

        {!loading && !error && projects.length === 0 && (
          <div className={styles.empty}>
            <p className={styles.emptyText}>
              まだプロジェクトがありません。GitHubリポジトリを登録して、チームの貢献の記録を始めましょう。
            </p>
            <Button variant="primary" onClick={() => setModalOpen(true)}>
              リポジトリを登録
            </Button>
          </div>
        )}

        {!loading && projects.length > 0 && (
          <div className={styles.grid}>
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </div>

      <NewProjectModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </AppShell>
  );
}
