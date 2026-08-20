"use client";

import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import type { Proposal, ProposalListItem } from "@/types";
import { formatAmount, formatPercent, toTenths } from "./allocation";
import { MAX_COMPARE } from "./useDistribution";
import styles from "./ProposalCompare.module.css";

type Props = {
  /** 選べる案（検討中・確定済みの両方） */
  options: ProposalListItem[];
  selectedIds: string[];
  onToggle: (proposalId: string) => void;
  details: Record<string, Proposal>;
  pendingIds: string[];
  errorById: Record<string, string>;
  onRetry: (proposalId: string) => void;
};

/**
 * 選んだ案を並べて比較する（画面7「複数案の作成・並べて比較する機能」）。
 *
 * **選んだものだけを取りに行く。** 以前は開いた瞬間に全件の詳細を並列で取り、全件を
 * 列にしていた。分配を何度もまわすチームでは案が数十件に育つので、開くたびにその数の
 * リクエストが飛び、列が数十本のテーブルが出る（実測: 確定25件で28列）。読めないうえ、
 * 比較したいのはたいてい2〜3案なので、要求されたものだけを取る形にした。
 *
 * 案ごとに重みが違いうるので、**重みの行を各案の見出しに出す**。数字だけを並べると
 * 「なぜこの案だと自分の配分が減るのか」が読めず、比較が説得ではなく力関係の話になる。
 * 重みを動かして複数案を比べられること自体が②固定を折る施策なので、その差が見えて
 * いないと比較する意味が薄い（docs/scoring_design.md）。
 *
 * 行（メンバー）は選んだ案の和集合。案によって分配対象から外れている人が居ても、
 * 行が消えると「その案では自分がどうなるのか」が読めなくなる。
 */
export function ProposalCompare({
  options,
  selectedIds,
  onToggle,
  details,
  pendingIds,
  errorById,
  onRetry,
}: Props) {
  const atLimit = selectedIds.length >= MAX_COMPARE;
  // 選んだ順に並べる。一覧の並び順に揃えると、チェックした瞬間に列が飛んで見える
  const shown = selectedIds
    .map((id) => details[id])
    .filter((p): p is Proposal => p !== undefined);

  const failed = selectedIds.filter((id) => errorById[id]);
  const loading = selectedIds.some((id) => pendingIds.includes(id));

  // 比率と金額の両方をサーバの値から引く。金額を比率から計算し直すと、比較の席に
  // 出る額と記録に残る額が食い違う
  const byProposal = shown.map(
    (p) =>
      new Map(
        p.items.map((i) => [
          i.github_login,
          { tenths: toTenths(i.ratio), amount: i.amount },
        ]),
      ),
  );
  const logins = [
    ...new Set(shown.flatMap((p) => p.items.map((i) => i.github_login))),
  ].sort((a, b) => a.localeCompare(b));

  return (
    <Card title="案の比較">
      <fieldset className={styles.picker}>
        <legend className={styles.legend}>
          並べる案を選ぶ（最大 <span className="num">{MAX_COMPARE}</span> 件）
        </legend>
        <div className={styles.options}>
          {options.map((p) => {
            const checked = selectedIds.includes(p.id);
            return (
              <label
                key={p.id}
                className={`${styles.option} ${!checked && atLimit ? styles.disabled : ""}`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  // 上限に達したら、選べないものは押せなくする。押してから
                  // 「選べません」と言うより、押せないほうが分かる
                  disabled={!checked && atLimit}
                  onChange={() => onToggle(p.id)}
                />
                <span className={styles.optionName}>{p.name}</span>
                {p.finalized && <span className={styles.finalized}>確定</span>}
              </label>
            );
          })}
        </div>
        {atLimit && (
          <p className={styles.limitNote}>
            これ以上は横に並べても読めないため、選び直してください。
          </p>
        )}
      </fieldset>

      {failed.map((id) => (
        <ErrorState
          key={id}
          message={errorById[id]}
          onRetry={() => onRetry(id)}
          retrying={pendingIds.includes(id)}
        />
      ))}

      {selectedIds.length === 0 ? (
        <p className={styles.empty}>比較する案を選んでください。</p>
      ) : shown.length === 0 && loading ? (
        <Spinner label="案を読み込んでいます…" />
      ) : shown.length === 0 ? null : (
        <>
          <div className={styles.scroll}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col" className={styles.memberHead}>
                    メンバー
                  </th>
                  {shown.map((p) => (
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
                    {shown.map((p, i) => {
                      const cell = byProposal[i].get(login);
                      if (cell === undefined) {
                        return (
                          <td key={p.id} className={styles.cell}>
                            <span className={styles.absent}>対象外</span>
                          </td>
                        );
                      }
                      const amount = cell.amount === null ? null : Number(cell.amount);
                      return (
                        <td key={p.id} className={styles.cell}>
                          <span className={`num ${styles.percent}`}>
                            {formatPercent(cell.tenths)}%
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
        </>
      )}
    </Card>
  );
}
