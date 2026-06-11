"use client";

import { Button } from "@/components/ui/Button";
import type { Summary } from "@/types";
import styles from "./ContributionSummary.module.css";

type Props = {
  summary: Summary | null;
  generating: boolean;
  error: string | null;
  onGenerate: () => void;
};

// Feature D: Claude APIによる貢献サマリー。AIの唯一の用途（スコアには使わない）
export function ContributionSummary({
  summary,
  generating,
  error,
  onGenerate,
}: Props) {
  return (
    <div className={styles.wrap}>
      {summary ? (
        <>
          <div className={styles.content}>
            {summary.content.split("\n").map(
              (line, i) =>
                line.trim() && (
                  <p key={i} className={styles.paragraph}>
                    {line}
                  </p>
                ),
            )}
          </div>
          <footer className={styles.footer}>
            <span className={`num ${styles.generatedAt}`}>
              生成 {new Date(summary.generated_at).toLocaleString("ja-JP")}
            </span>
            <Button
              variant="ghost"
              size="s"
              onClick={onGenerate}
              loading={generating}
            >
              再生成
            </Button>
          </footer>
        </>
      ) : (
        <div className={styles.empty}>
          <p className={styles.emptyText}>
            コミット・PRの内容から、このメンバーの貢献を文章で記録します。
            スコアの根拠の補完や、実績の証明に使えます。
          </p>
          <Button onClick={onGenerate} loading={generating}>
            サマリーを生成する
          </Button>
        </div>
      )}
      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}
