import Link from "next/link";
import type { ProjectListItem } from "@/types";
import styles from "./ProjectCard.module.css";

type Props = {
  project: ProjectListItem;
};

export function ProjectCard({ project }: Props) {
  return (
    <Link
      href={`/projects/${project.id}/dashboard`}
      className={styles.card}
    >
      <div className={styles.name}>{project.name}</div>
      <div className={`${styles.repo} num`}>
        {project.repo_owner}/{project.repo_name}
      </div>
      <div className={`${styles.members} num`}>
        {project.member_count} members
      </div>
    </Link>
  );
}
