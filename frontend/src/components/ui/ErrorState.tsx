"use client";

import { Button } from "./Button";
import styles from "./ErrorState.module.css";

type Props = {
  message: string;
  /** 渡すとその場に再試行ボタンを出す。省略時は文言だけ */
  onRetry?: () => void;
  retrying?: boolean;
};

/**
 * カードの中身が取れなかったときの表示（#13 のデザインレビューからの申し送り・#14）。
 *
 * 赤い1行だけを置かないのが要点。エラーが出ても Card のタイトルは呼び出し側に残して
 * もらう前提で、「そこに何があるはずだったか」を消さない。再試行は画面上部の一括
 * 再読み込みではなく**失敗した場所**に置く（変化ログのエラーは最下部に出るのに、
 * ボタンだけが最上部にある状態を避ける）。
 */
export function ErrorState({ message, onRetry, retrying = false }: Props) {
  return (
    <div className={styles.wrap} role="alert">
      <p className={styles.message}>{message}</p>
      {onRetry && (
        <Button
          variant="secondary"
          size="s"
          onClick={onRetry}
          loading={retrying}
        >
          再試行
        </Button>
      )}
    </div>
  );
}
