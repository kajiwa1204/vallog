"use client";

import { useState } from "react";
import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import type { Summary } from "@/types";
import styles from "./SummaryPanel.module.css";

type Props = {
  projectId: string;
  summaries: Summary[];
};

// 分配の議論はスコアではなく貢献サマリーから始める（設計思想）
export function SummaryPanel({ projectId, summaries }: Props) {
  const [openLogin, setOpenLogin] = useState<string | null>(
    summaries[0]?.github_login ?? null,
  );

  if (summaries.length === 0) {
    return (
      <p className={styles.empty}>
        貢献サマリーがまだ生成されていません。
        各メンバーの詳細画面（ダッシュボード → メンバー名）から生成すると、
        ここに表示され、分配の議論の土台になります。
      </p>
    );
  }

  return (
    <div className={styles.list}>
      {summaries.map((s) => {
        const open = openLogin === s.github_login;
        return (
          <article key={s.github_login} className={styles.item}>
            <button
              className={styles.head}
              onClick={() => setOpenLogin(open ? null : s.github_login)}
              aria-expanded={open}
            >
              <Avatar login={s.github_login} size={26} />
              <span className={`num ${styles.login}`}>{s.github_login}</span>
              <span className={styles.preview}>
                {open ? "" : s.content.slice(0, 60) + "…"}
              </span>
              <span className={styles.chevron}>{open ? "−" : "+"}</span>
            </button>
            {open && (
              <div className={styles.body}>
                {s.content.split("\n").map(
                  (line, i) =>
                    line.trim() && (
                      <p key={i} className={styles.paragraph}>
                        {line}
                      </p>
                    ),
                )}
                <Link
                  href={`/projects/${projectId}/members/${s.github_login}`}
                  className={styles.detailLink}
                >
                  根拠データを見る →
                </Link>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
