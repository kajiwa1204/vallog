import styles from "./Spinner.module.css";

export function Spinner({ label = "読み込み中…" }: { label?: string }) {
  return (
    <div className={styles.wrap} role="status">
      <span className={styles.ring} aria-hidden />
      <span className={styles.label}>{label}</span>
    </div>
  );
}
