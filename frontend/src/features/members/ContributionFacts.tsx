"use client";

import { ReactNode } from "react";
import { Card } from "@/components/ui/Card";
import { formatElapsed } from "@/lib/duration";
import type { Breakdown, ContributionFacts as Facts } from "./activity";
import styles from "./ContributionFacts.module.css";

type Props = {
  facts: Facts;
  isMe: boolean;
  // 集計の母数と、それが記録の全部かどうか
  countedEntries: number;
  truncated: boolean;
};

function Stat({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
}) {
  return (
    <div className={styles.stat}>
      <span className={styles.label}>{label}</span>
      <span className={`num ${styles.value}`}>{value}</span>
      {detail && <span className={styles.detail}>{detail}</span>}
    </div>
  );
}

/** 排他な内訳を並べる。和は必ず合計に一致する（activity.ts の breakdownOf を参照） */
function formatBreakdown(parts: Breakdown[]): string | null {
  if (parts.length === 0) return null;
  return parts.map((p) => `${p.label} ${p.count}`).join(" ・ ");
}

/**
 * 各指標の生データ（#14）。
 *
 * カテゴリ別スコアも総合スコアも出さない（docs/scoring_design.md「Goodhart対策と
 * スコアの事後開示」。開示は画面7）。ここに並ぶのは重み付けも順位付けもしない件数と
 * 時間だけで、他のメンバーの数字とも並べない。
 *
 * すべて下の変化ログに並んでいる行を数えた値。「自分の貢献が正しく記録されているか」を
 * 確かめるのがこの画面の用途なので、数字を見て一覧を数えれば必ず一致する必要がある。
 * その保証を成り立たせるために、母数（何件から数えたか）を画面にも出す。
 */
export function ContributionFacts({
  facts,
  isMe,
  countedEntries,
  truncated,
}: Props) {
  return (
    <Card title="記録されている数">
      <div className={styles.grid}>
        <Stat
          label="出したPR"
          value={facts.prsOpened}
          detail={formatBreakdown(facts.prBreakdown)}
        />
        <Stat
          // 絞り込みが起票者∪担当者なので、この数もその両方を含む。数え方をそのまま
          // 名前にする。どちらで関わったかは一覧の各行が「起票 ◯◯ ・ 担当 ◯◯」で示す
          label="Issue（起票・担当）"
          value={facts.issues}
          detail={formatBreakdown(facts.issueBreakdown)}
        />
        <Stat
          label="出したレビュー"
          value={facts.reviews}
          detail={formatBreakdown(facts.reviewBreakdown)}
        />
        <Stat
          label="完了IssueのSP"
          value={facts.storyPointsCompleted ?? "—"}
          detail={
            facts.storyPointsCompleted === null
              ? "SPラベルの付いた完了Issueなし"
              : "ラベルの値の合計"
          }
        />
        <Stat
          label="レビューを返すまで"
          value={
            facts.medianResponseHours === null
              ? "—"
              : formatElapsed(facts.medianResponseHours)
          }
          detail="中央値・PRごとの初回・PR作成から"
        />
        <Stat
          label={isMe ? "あなたのPRに初レビューが付くまで" : "PRに初レビューが付くまで"}
          value={
            facts.medianFirstReviewHours === null
              ? "—"
              : formatElapsed(facts.medianFirstReviewHours)
          }
          detail="中央値・チームの応答"
        />
      </div>

      {facts.prsWithoutReview > 0 && (
        <p className={styles.callout}>
          他者レビューが付いていないPRが {facts.prsWithoutReview} 件あります。
          {isMe && "下の一覧から該当のPRをGitHubで開けます。"}
        </p>
      )}

      <p className={styles.source}>
        {truncated ? "下に並ぶ直近 " : "下に並ぶ "}
        <span className="num">{countedEntries}</span> 件の記録を数えた値です。
        {/* 「もっと見る」で続きが読めるとは言えない。1リクエストの上限は
            バックエンドが200件で、そこに達したらこの画面からは取りに行けない */}
        {truncated && "これより古い記録は数に入っていません。"}
      </p>
    </Card>
  );
}
