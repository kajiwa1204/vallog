import Link from "next/link";
import styles from "./TotalScoreBarChart.module.css";
import type { MemberScore } from "@/types";
import { Avatar } from "@/components/ui/Avatar";

type Props = {
  scores: MemberScore[];
  projectId: string;
};

export function TotalScoreBarChart({ scores, projectId }: Props) {
  const max = Math.max(...scores.map((s) => s.total), 1);
  return (
    <ol className={styles.list}>
      {scores.map((s, i) => (
        <li key={s.login}>
          <Link
            href={`/projects/${projectId}/members/${s.login}`}
            className={styles.row}
          >
            <span className={styles.rank}>#{i + 1}</span>
            <Avatar src={s.avatarUrl} alt={s.name} size={28} />
            <span className={styles.name}>{s.name}</span>
            <div className={styles.barOuter}>
              <div className={styles.barFill} style={{ width: `${(s.total / max) * 100}%` }} />
            </div>
            <span className={styles.value}>{s.total}</span>
            <span className={styles.unit}>pts</span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
