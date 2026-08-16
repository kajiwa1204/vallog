"use client";

import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import type { Proposal } from "@/types";
import { amountFor, formatAmount, formatPercent, toTenths } from "./allocation";
import { PanelError } from "./PanelError";
import styles from "./ProposalCompare.module.css";

type Props = {
  proposals: Proposal[] | null;
  error: string | null;
  onRetry: () => void;
};

/**
 * 複数案を並べて比較する（画面7「複数案の作成・並べて比較する機能」）。
 *
 * 案ごとに重みが違いうるので、**重みの行を各案の見出しに出す**。数字だけを並べると
 * 「なぜこの案だと自分の配分が減るのか」が読めず、比較が説得ではなく力関係の話になる。
 * 重みを動かして複数案を比べられること自体が Goodhart の②固定を折る施策なので、
 * その差が見えていないと比較する意味が薄い（docs/scoring_design.md）。
 *
 * 行（メンバー）は全案の和集合。案によって分配対象から外れている人が居ても、
 * 行が消えると「その案では自分がどうなるのか」が読めなくなる。
 */
export function ProposalCompare({ proposals, error, onRetry }: Props) {
  if (error) {
    return (
      <Card title="案の比較">
        <PanelError message={error} onRetry={onRetry} />
      </Card>
    );
  }
  if (proposals === null) {
    return (
      <Card title="案の比較">
        <Spinner label="案を読み込んでいます…" />
      </Card>
    );
  }
  if (proposals.length === 0) {
    return (
      <Card title="案の比較">
        <p className={styles.empty}>比較できる案がありません。</p>
      </Card>
    );
  }

  // 各案の配分を引くための索引。行の描画で毎回 find しない
  const byProposal = proposals.map(
    (p) => new Map(p.items.map((i) => [i.github_login, toTenths(i.ratio)])),
  );
  const logins = [
    ...new Set(proposals.flatMap((p) => p.items.map((i) => i.github_login))),
  ].sort((a, b) => a.localeCompare(b));

  return (
    <Card title="案の比較">
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col" className={styles.memberHead}>
                メンバー
              </th>
              {proposals.map((p) => (
                <th key={p.id} scope="col" className={styles.proposalHead}>
                  <span className={styles.proposalName}>{p.name}</span>
                  <span className={`num ${styles.weights}`}>
                    {p.weights.activity} / {p.weights.speed} / {p.weights.quality}
                  </span>
                  <span className={`num ${styles.amountHead}`}>
                    {p.total_amount === null
                      ? "総額未入力"
                      : `¥${formatAmount(Number(p.total_amount))}`}
                  </span>
                  {p.finalized && <span className={styles.finalized}>確定済み</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logins.map((login) => (
              <tr key={login}>
                <th scope="row" className={`num ${styles.member}`}>
                  {login}
                </th>
                {proposals.map((p, i) => {
                  const tenths = byProposal[i].get(login);
                  if (tenths === undefined) {
                    return (
                      <td key={p.id} className={styles.cell}>
                        <span className={styles.absent}>対象外</span>
                      </td>
                    );
                  }
                  const amount = amountFor(p.total_amount, tenths);
                  return (
                    <td key={p.id} className={styles.cell}>
                      <span className={`num ${styles.percent}`}>
                        {formatPercent(tenths)}%
                      </span>
                      {amount !== null && (
                        <span className={`num ${styles.amount}`}>
                          ¥{formatAmount(amount)}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={styles.note}>
        見出しの3つの数字は、その案のカテゴリ重み（活動量 / スピード / 品質）です。
      </p>
    </Card>
  );
}
