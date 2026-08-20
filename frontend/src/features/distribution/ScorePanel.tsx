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
  // 全員が0のカテゴリ。棒がどれも空になるので、理由を言わないと読めない
  const emptyCategories =
    state.kind === "ready"
      ? CATEGORIES.filter((c) =>
          state.scores.members.every((m) => m.categories[c.key] === 0),
        ).map((c) => c.label)
      : [];

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
          {/* 「案を作ったときの値」ではない。GitHubのキャッシュから都度計算する
              ライブの値なので、案を作ってから活動が進めば変わる */}
          <p className={styles.lead}>
            カテゴリごとの棒は、そのカテゴリでのチーム内シェアです（各カテゴリで全員の合計が100%）。
            右上の総合は、選択中の案の重み（活動量 {state.scores.weights.activity}% ・ スピード{" "}
            {state.scores.weights.speed}% ・ 品質 {state.scores.weights.quality}%）で合成した値。
            分配額はここから自動では決まりません。
          </p>

          {state.scores.members.length === 0 ? (
            <p className={styles.empty}>まだスコアの対象になる活動がありません。</p>
          ) : (
            <ul className={styles.members}>
              {state.scores.members.map((member) => (
                <li key={member.github_login} className={styles.member}>
                  <div className={styles.memberHead}>
                    <span className={`num ${styles.login}`}>{member.github_login}</span>
                    {/* カテゴリ値と同じ右揃え列に並ぶので、母数が違うことをラベルで
                        分ける（総合＝全員で100%、カテゴリ＝そのカテゴリで100%） */}
                    <span className={styles.totalWrap}>
                      <span className={styles.totalLabel}>総合</span>
                      <span className={`num ${styles.total}`}>
                        {percent(member.total)}
                      </span>
                    </span>
                  </div>

                  {/* カテゴリごとに独立したバーを、**全メンバーで同じ左端**から引く。
                      1本の積み上げバーだと、幅が flexGrow で必ず全幅を埋めるうえ
                      （長さが何も意味しない）、セグメントの開始位置が人ごとに違って
                      「この指標で誰が多いか」を横に読めなかった */}
                  <div className={styles.categories}>
                    {CATEGORIES.map((c) => {
                      const share = member.categories[c.key];
                      return (
                        <div key={c.key} className={styles.category}>
                          <span className={styles.categoryLabel}>{c.short}</span>
                          {/* 左右に「活動量」「61.1%」が地の文であるので、バーに
                              aria-label を付けると三重に読まれる。バーは装飾に徹する */}
                          <span className={styles.track} aria-hidden="true">
                            <span
                              className={styles.fill}
                              style={{ width: `${share * 100}%`, background: c.color }}
                            />
                          </span>
                          <span className={`num ${styles.categoryValue}`}>
                            {percent(share)}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <Facts member={member} />
                </li>
              ))}
            </ul>
          )}

          {/* 全員0のカテゴリは重みが他へ再配分される（services/scoring.py）。
              棒が全部空なのを「誰も活躍していない」と読まれないように言っておく */}
          {emptyCategories.length > 0 && (
            <p className={styles.factsNote}>
              {emptyCategories.join("・")}
              は元になるデータがないため、その重みは他のカテゴリに配分されています。
            </p>
          )}

          {/* 生事実と総合スコアは順位が逆転しうる（SPが最多でも総合は3位、など）。
              事実は実数、総合は3カテゴリを重みで合成した相対値で、別のものを見ている。
              説明が無いと分配の席で最初に突かれる */}
          <p className={styles.factsNote}>
            下段の数字は重み付けをしていない実数です。総合スコアは3カテゴリを相対化して重みで合成した値なので、順位が一致しないことがあります。
          </p>

          {/* 寄与の小さい人ほど空のトラックが並ぶ。正確さは落とさないが、この画面は
              face-to-face の分配の席で開かれるので、数字に現れない貢献の受け皿が
              ここにも要る（分配案カードの出発点ノートと理由欄にしか無かった） */}
          <p className={styles.factsNote}>
            設計の相談・ドキュメント・運用など、GitHubに残らない貢献はここには出ません。下の分配案で理由を添えて反映できます。
          </p>

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
