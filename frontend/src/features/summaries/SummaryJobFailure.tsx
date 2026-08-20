import type { SummaryJob } from "@/types";
import { summaryJobFailureMessage } from "./summaryJobMessages";
import styles from "./SummaryJobFailure.module.css";

type Props = {
  job: SummaryJob;
  className?: string;
};

export function SummaryJobFailure({
  job,
  className,
}: Props) {
  return (
    <div className={className}>
      <p className={styles.message} role="alert">
        前回の生成に失敗しました。再生成できます。
      </p>
      <details className={styles.details}>
        <summary className={styles.summary}>失敗理由を確認</summary>
        <p className={styles.reason}>{summaryJobFailureMessage(job.error)}</p>
      </details>
    </div>
  );
}
