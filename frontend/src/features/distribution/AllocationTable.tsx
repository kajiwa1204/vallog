"use client";

import { useEffect, useMemo, useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import type { Proposal } from "@/types";
import styles from "./AllocationTable.module.css";

type Props = {
  proposal: Proposal;
  onSave: (
    items: { github_login: string; ratio: string }[],
  ) => void;
};

function toPercent(ratio: string): number {
  return Math.round(parseFloat(ratio) * 1000) / 10;
}

// メンバー全員が数値を自由に編集できる。保存時に理由の入力を必須とする
export function AllocationTable({ proposal, onSave }: Props) {
  const locked = proposal.status === "agreed";
  const [percents, setPercents] = useState<Record<string, number>>({});

  useEffect(() => {
    setPercents(
      Object.fromEntries(
        proposal.items.map((i) => [i.github_login, toPercent(i.ratio)]),
      ),
    );
  }, [proposal]);

  const totalPercent = useMemo(
    () =>
      Math.round(
        Object.values(percents).reduce((sum, v) => sum + (v || 0), 0) * 10,
      ) / 10,
    [percents],
  );

  const dirty = useMemo(
    () =>
      proposal.items.some(
        (i) => toPercent(i.ratio) !== (percents[i.github_login] ?? 0),
      ),
    [proposal, percents],
  );

  const totalAmount =
    proposal.total_amount !== null ? parseFloat(proposal.total_amount) : null;
  const valid = Math.abs(totalPercent - 100) < 0.5;

  return (
    <div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.thMember}>メンバー</th>
            <th className={styles.thRatio}>分配比率</th>
            <th className={styles.thBar} aria-hidden />
            {totalAmount !== null && (
              <th className={styles.thAmount}>金額</th>
            )}
          </tr>
        </thead>
        <tbody>
          {proposal.items.map((item) => {
            const pct = percents[item.github_login] ?? 0;
            return (
              <tr key={item.github_login}>
                <td className={styles.tdMember}>
                  <Avatar
                    login={item.github_login}
                    url={item.avatar_url}
                    size={26}
                  />
                  <span className={`num ${styles.login}`}>
                    {item.github_login}
                  </span>
                </td>
                <td className={styles.tdRatio}>
                  <span className={styles.ratioInputWrap}>
                    <input
                      className={`num ${styles.ratioInput}`}
                      type="number"
                      min={0}
                      max={100}
                      step={0.1}
                      value={pct}
                      disabled={locked}
                      onChange={(e) =>
                        setPercents((prev) => ({
                          ...prev,
                          [item.github_login]: parseFloat(e.target.value) || 0,
                        }))
                      }
                    />
                    <span className={styles.unit}>%</span>
                  </span>
                </td>
                <td className={styles.tdBar}>
                  <span className={styles.track}>
                    <span
                      className={styles.bar}
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </span>
                </td>
                {totalAmount !== null && (
                  <td className={`num ${styles.tdAmount}`}>
                    ¥{Math.round((totalAmount * pct) / 100).toLocaleString()}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td className={styles.tfLabel}>合計</td>
            <td
              className={`num ${styles.tfTotal} ${valid ? "" : styles.invalid}`}
            >
              {totalPercent.toFixed(1)}%
            </td>
            <td />
            {totalAmount !== null && (
              <td className={`num ${styles.tdAmount}`}>
                ¥{totalAmount.toLocaleString()}
              </td>
            )}
          </tr>
        </tfoot>
      </table>

      {!locked && (
        <div className={styles.actions}>
          {!valid && (
            <span className={styles.warn}>合計を100%にしてください</span>
          )}
          <Button
            size="s"
            disabled={!dirty || !valid}
            onClick={() =>
              onSave(
                proposal.items.map((i) => ({
                  github_login: i.github_login,
                  ratio: (
                    (percents[i.github_login] ?? 0) / 100
                  ).toFixed(6),
                })),
              )
            }
          >
            調整を保存…
          </Button>
        </div>
      )}
    </div>
  );
}
