import styles from "./EditHistoryTimeline.module.css";
import type { EditLog } from "./useDistribution";
import { Avatar } from "@/components/ui/Avatar";
import { formatYen } from "@/lib/mockData";

type Props = { logs: EditLog[] };

const formatRelative = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return "たった今";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}分前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour}時間前`;
  return new Date(iso).toLocaleString("ja-JP", { month: "short", day: "numeric" });
};

export function EditHistoryTimeline({ logs }: Props) {
  if (logs.length === 0) {
    return (
      <div className={styles.empty}>
        <span className={styles.emptyIcon} aria-hidden>📜</span>
        <div>
          <div className={styles.emptyTitle}>まだ手動調整はありません</div>
          <div className={styles.emptyHint}>
            金額を編集すると、変更内容と理由がここに時系列で記録され、全員に公開されます。
          </div>
        </div>
      </div>
    );
  }

  return (
    <ol className={styles.timeline}>
      {logs.map((log) => {
        const diff = log.to - log.from;
        return (
          <li key={log.id} className={styles.item}>
            <div className={styles.dot} />
            <div className={styles.body}>
              <div className={styles.head}>
                <Avatar src={log.editedByAvatar} alt={log.editedBy} size={22} />
                <span className={styles.editor}>{log.editedBy}</span>
                <span className={styles.verb}>が</span>
                <span className={styles.target}>{log.name}</span>
                <span className={styles.verb}>の分配額を調整</span>
                <span className={styles.time}>{formatRelative(log.editedAt)}</span>
              </div>
              <div className={styles.change}>
                <span className={styles.fromAmount}>{formatYen(log.from)}</span>
                <span className={styles.arrow}>→</span>
                <span className={styles.toAmount}>{formatYen(log.to)}</span>
                <span
                  className={[
                    styles.diff,
                    diff > 0 ? styles.diffUp : styles.diffDown,
                  ].join(" ")}
                >
                  ({diff > 0 ? "+" : "−"}{formatYen(Math.abs(diff))})
                </span>
              </div>
              <blockquote className={styles.reason}>{log.reason}</blockquote>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
