"use client";

import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { CATEGORIES } from "@/constants";
import { formatElapsed } from "@/lib/duration";
import type { MemberScore } from "@/types";
import { PanelError } from "./PanelError";
import type { ScoreState } from "./useDistribution";
import styles from "./ScorePanel.module.css";

type Props = {
  state: ScoreState;
  onRetry: () => void;
  /** 選択中の案が確定済み。非開示に戻った理由を言い分けるために使う */
  selectedIsFinalized: boolean;
  /** 選択中の案が未確定なのに非開示＝30日を過ぎて議論が立ち消えている */
  disclosureLapsed: boolean;
  /** 確定した分配が1件でもある。過去の記録がどこにあるかを案内するために使う */
  hasFinalized: boolean;
};

function percent(share: number): string {
  return `${(share * 100).toFixed(1)}%`;
}

/**
 * 生事実の1行。**ラベルは types/index.ts の MemberFacts のフィールド名から外さない。**
 *
 * scoring は SP を担当者にのみ配るが、変化ログの絞り込みはIssueだけ起票者∪担当者。
 * 「SP」とだけ書くと、同じ名前で母集合の違う数が別の画面に並ぶことになる。
 */
function Facts({ member }: { member: MemberScore }) {
  const f = member.facts;
  const items: [string, string][] = [
    ["担当した完了IssueのSP", String(f.story_points_earned)],
    ["出したPR", String(f.pull_requests_authored)],
    ["出したレビュー", String(f.reviews_submitted)],
    ["自分のPRの再オープン", String(f.pull_requests_reopened)],
    [
      "レビューを返すまで",
      f.avg_review_turnaround_hours === null
        ? "—"
        : formatElapsed(f.avg_review_turnaround_hours),
    ],
  ];
  return (
    <ul className={styles.facts}>
      {items.map(([label, value]) => (
        <li key={label} className={styles.fact}>
          <span className={styles.factLabel}>{label}</span>
          <span className={`num ${styles.factValue}`}>{value}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * スコア（画面7）。**アプリ全体でスコアが出る唯一の場所**
 * （docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
 *
 * カードの見出しは「スコア」だけにしてある。「（補助情報）」と添えていたが、
 * スコアを下部に小さく置いていた頃の名残で、貢献サマリーと同列に並べたいまの
 * レイアウトとは矛盾する。**位置で「補助」を表現しなくなったのに、括弧書きだけが
 * 残っている状態**だった。分配額がここから自動で決まらないことは、下のリード文が
 * そのまま言っている（括弧書きより具体的で、読み手の行動に変換できる）。
 *
 * 各メンバーには根拠として生事実を添える。振り返りの「レシート」は点数分解
 * （+0.06 等）ではなく事実の積み上げで示す、というのがこの画面の方針のため。
 */
export function ScorePanel({
  state,
  onRetry,
  selectedIsFinalized,
  disclosureLapsed,
  hasFinalized,
}: Props) {
  return (
    <Card title="スコア">
      {state.kind === "loading" && <Spinner label="スコアを読み込んでいます…" />}

      {/* 403 は失敗ではなく設計どおりの状態（#100）。赤いエラーにも再試行にもしない。
          押しても案を作るまで結果は変わらず、原因も「権限がない」ではない */}
      {state.kind === "undisclosed" && (
        <div className={styles.undisclosed}>
          <p className={styles.undisclosedLead}>
            {selectedIsFinalized
              ? "この分配は確定済みのため、スコアは表示していません。"
              : disclosureLapsed
                ? "この案は30日以上更新されていないため、スコアは表示していません。"
                : "スコアは、検討中の分配案があるときに表示されます。"}
          </p>
          <p className={styles.undisclosedBody}>
            {selectedIsFinalized
              ? "確定した配分は下の表に残っています。もう一度検討するときは新しい案を作成してください。"
              : disclosureLapsed
                ? "配分か重みを保存すると、また表示されます。"
                : hasFinalized
                  ? "スコアは分配を話し合うための材料なので、分配案を作成すると表示されます。過去に確定した分配は下の「確定した分配」に残っています。"
                  : "スコアは分配を話し合うための材料なので、分配案を作成すると表示されます。"}
          </p>
        </div>
      )}

      {state.kind === "error" && (
        <PanelError
          message={state.message}
          onRetry={state.retryable ? onRetry : undefined}
        />
      )}

      {state.kind === "ready" && (
        <>
          <p className={styles.lead}>
            案を作ったときの出発点になった値です。分配額はここから自動では決まりません。
            重みは 活動量 {state.scores.weights.activity}% ・ スピード{" "}
            {state.scores.weights.speed}% ・ 品質 {state.scores.weights.quality}%。
          </p>

          {state.scores.members.length === 0 ? (
            <p className={styles.empty}>まだスコアの対象になる活動がありません。</p>
          ) : (
            <ul className={styles.members}>
              {state.scores.members.map((member) => (
                <li key={member.github_login} className={styles.member}>
                  <div className={styles.memberHead}>
                    <span className={`num ${styles.login}`}>{member.github_login}</span>
                    <span className={`num ${styles.total}`}>
                      {percent(member.total)}
                    </span>
                  </div>

                  <div
                    className={styles.bar}
                    role="img"
                    aria-label={CATEGORIES.map(
                      (c) => `${c.label} ${percent(member.categories[c.key])}`,
                    ).join("、")}
                  >
                    {CATEGORIES.map((c) => (
                      <span
                        key={c.key}
                        className={styles.segment}
                        style={{
                          flexGrow: member.categories[c.key],
                          background: c.color,
                        }}
                      />
                    ))}
                    {/* 全カテゴリ0のメンバーで幅が潰れないように余白を持たせる */}
                    <span className={styles.segmentRest} />
                  </div>

                  <Facts member={member} />
                </li>
              ))}
            </ul>
          )}

          <p className={styles.legend}>
            {CATEGORIES.map((c) => (
              <span key={c.key} className={styles.legendItem}>
                <span className={styles.swatch} style={{ background: c.color }} />
                {c.label}
              </span>
            ))}
          </p>
        </>
      )}
    </Card>
  );
}
