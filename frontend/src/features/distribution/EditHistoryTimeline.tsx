"use client";

import { Avatar } from "@/components/ui/Avatar";
import type { EditLog } from "@/types";
import styles from "./EditHistoryTimeline.module.css";

function pct(ratio: string): string {
  return `${(parseFloat(ratio) * 100).toFixed(1)}%`;
}

type Change = { login: string; before: string | null; after: string | null };

function diffItems(log: EditLog): Change[] {
  const before = new Map(
    log.before_items.items.map((i) => [i.github_login, i.ratio]),
  );
  const after = new Map(
    log.after_items.items.map((i) => [i.github_login, i.ratio]),
  );
  const logins = [...new Set([...before.keys(), ...after.keys()])].sort();
  return logins
    .map((login) => ({
      login,
      before: before.get(login) ?? null,
      after: after.get(login) ?? null,
    }))
    .filter(
      (c) =>
        c.before === null ||
        c.after === null ||
        parseFloat(c.before) !== parseFloat(c.after),
    );
}

// git log風の編集履歴。誰がいつ何を変更したか・その理由を全員に公開する（社会的抑止力）
export function EditHistoryTimeline({ logs }: { logs: EditLog[] }) {
  if (logs.length === 0) {
    return <p className={styles.empty}>まだ編集履歴はありません。</p>;
  }

  return (
    <ol className={styles.timeline}>
      {logs.map((log) => {
        const changes = diffItems(log);
        return (
          <li key={log.id} className={styles.entry}>
            <span className={styles.dot} aria-hidden />
            <div className={styles.body}>
              <header className={styles.head}>
                <Avatar
                  login={log.editor_login}
                  url={log.editor_avatar_url}
                  size={22}
                />
                <span className={`num ${styles.editor}`}>
                  {log.editor_login}
                </span>
                <span className={`num ${styles.date}`}>
                  {new Date(log.created_at).toLocaleString("ja-JP")}
                </span>
              </header>
              <p className={styles.reason}>{log.reason}</p>
              {changes.length > 0 && (
                <ul className={styles.changes}>
                  {changes.map((c) => (
                    <li key={c.login} className={`num ${styles.change}`}>
                      <span className={styles.changeLogin}>{c.login}</span>
                      <span className={styles.before}>
                        {c.before !== null ? pct(c.before) : "—"}
                      </span>
                      <span className={styles.arrow}>→</span>
                      <span className={styles.after}>
                        {c.after !== null ? pct(c.after) : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
