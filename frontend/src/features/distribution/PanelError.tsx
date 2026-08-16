"use client";

import { Button } from "@/components/ui/Button";
import styles from "./PanelError.module.css";

type Props = {
  message: string;
  /** 渡すとその場に再試行ボタンを出す。省略時は文言だけ */
  onRetry?: () => void;
  retrying?: boolean;
};

/**
 * カードの中身が取れなかったときの表示。
 *
 * **暫定。#113（画面5）で `components/ui/ErrorState` として同じものが作られており、
 * マージされ次第そちらへ差し替えてこのファイルは削除する。** #113 のレビューを
 * 待たずに着手したため、同名のファイルを別内容で作らないようここに置いている。
 *
 * 要点は #113 の ErrorState と同じ。赤い1行だけを置かず、Card のタイトルは呼び出し側に
 * 残してもらって「そこに何があるはずだったか」を消さない。再試行は画面上部の一括
 * 再読み込みではなく**失敗した場所**に置く。
 */
export function PanelError({ message, onRetry, retrying = false }: Props) {
  return (
    <div className={styles.wrap} role="alert">
      <p className={styles.message}>{message}</p>
      {onRetry && (
        <Button variant="secondary" size="s" onClick={onRetry} loading={retrying}>
          再試行
        </Button>
      )}
    </div>
  );
}
