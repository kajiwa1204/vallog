"use client";

import { Card } from "@/components/ui/Card";
import { type ActivityWeek, weekTotal } from "./activity";
import styles from "./ActivityChart.module.css";

const KINDS = [
  { key: "pullRequests", label: "PR", color: "var(--green)" },
  { key: "issues", label: "Issue", color: "var(--ochre)" },
  { key: "reviews", label: "レビュー", color: "var(--slate)" },
] as const;

function formatWeek(weekStart: string): string {
  // ローカル日付として組み立てられた文字列。Date に通すとUTC解釈で1日ずれる
  const [, month, day] = weekStart.split("-");
  return `${Number(month)}/${Number(day)}`;
}

type Props = {
  weeks: ActivityWeek[];
  truncated: boolean;
  // weeks が空のとき、記録そのものがいつのものかを言うために使う
  latestAt: string | null;
};

/**
 * 活動量の推移（#14）。週の始まり（月曜）ごとの件数。
 *
 * ダッシュボードの活動リズム（TeamPulse）が日次なのに対して週次にしているのは、
 * 個人の活動がチームより疎で、日次だと大半が空バーになりリズムが読めないため。
 *
 * 描画は TeamPulse とほぼ同型で、CSSを含めて実質的に重複している。統合していないのは
 * 未マージPRを7本抱えた状態で #13 のファイルに触ると衝突面が広がるという**運用上の
 * 都合**であって、設計上の理由ではない。取得層（サーバ畳み込みの日次／クライアント
 * 畳み込みの週次）が違うだけで描画層に違いは無いので、スタックが解消したら
 * `{label, segments}[]` を受ける表示コンポーネント1つに寄せること。
 *
 * 高さは件数そのもの。他のメンバーと並べず、順位も出さない
 * （docs/scoring_design.md「Goodhart対策とスコアの事後開示」）。
 */
export function ActivityChart({ weeks, truncated, latestAt }: Props) {
  const max = Math.max(...weeks.map(weekTotal), 1);
  const total = weeks.reduce((sum, week) => sum + weekTotal(week), 0);

  return (
    <Card
      title="活動量の推移"
      actions={
        weeks.length > 0 && (
          <span className={`num ${styles.range}`}>
            {formatWeek(weeks[0].weekStart)} 〜{" "}
            {formatWeek(weeks[weeks.length - 1].weekStart)} の週ごと
          </span>
        )
      }
    >
      {weeks.length === 0 ? (
        // 0のバーを12本並べて「直近12週で0件」と言うと、その真横で「N件を数えた」と
        // 言っているカードと矛盾した印象になる。記録がいつのものかを言って畳む
        <p className={styles.empty}>
          直近12週にこの人の記録はありません。
          {latestAt !== null &&
            `最新の記録は ${new Date(latestAt).toLocaleDateString("ja-JP", {
              year: "numeric",
              month: "numeric",
              day: "numeric",
            })} です。`}
        </p>
      ) : (
        <>
          <div
            className={styles.chart}
            role="img"
            aria-label={`直近${weeks.length}週で${total}件の記録`}
          >
            {weeks.map((week) => {
              const weekly = weekTotal(week);
              return (
                <div key={week.weekStart} className={styles.column}>
                  <div className={styles.track}>
                    <div
                      className={styles.bar}
                      style={{ height: `${(weekly / max) * 100}%` }}
                      title={`${formatWeek(week.weekStart)} の週 — PR ${week.pullRequests} / Issue ${week.issues} / レビュー ${week.reviews}`}
                    >
                      {KINDS.map((kind) => (
                        <span
                          key={kind.key}
                          className={styles.segment}
                          style={{ flexGrow: week[kind.key], background: kind.color }}
                        />
                      ))}
                    </div>
                  </div>
                  <span className={`num ${styles.tick}`}>
                    {formatWeek(week.weekStart)}
                  </span>
                </div>
              );
            })}
          </div>

          <table className="visually-hidden">
            <caption>週別の活動件数</caption>
            <thead>
              <tr>
                <th scope="col">週</th>
                {KINDS.map((kind) => (
                  <th key={kind.key} scope="col">
                    {kind.label}
                  </th>
                ))}
                <th scope="col">合計</th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((week) => (
                <tr key={week.weekStart}>
                  <th scope="row">{formatWeek(week.weekStart)} の週</th>
                  <td>{week.pullRequests}</td>
                  <td>{week.issues}</td>
                  <td>{week.reviews}</td>
                  <td>{weekTotal(week)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className={styles.legend}>
            {KINDS.map((kind) => (
              <span key={kind.key} className={styles.legendItem}>
                <span className={styles.swatch} style={{ background: kind.color }} />
                {kind.label}
              </span>
            ))}
          </div>

          {truncated && (
            <p className={styles.note}>
              読み込み済みの記録の範囲で描いています。これより古い週は含まれていません。
            </p>
          )}
        </>
      )}
    </Card>
  );
}
