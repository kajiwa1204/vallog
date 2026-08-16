"use client";

import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import type { EditLog, ProposalSnapshot } from "@/types";
import { formatAmount, formatPercent, toTenths } from "./allocation";
import styles from "./EditHistoryTimeline.module.css";

type Props = {
  logs: EditLog[];
};

type Change = {
  label: string;
  before: string;
  after: string;
};

/**
 * 変更前後のスナップショットから「何が変わったか」を作る。
 *
 * **各項目をちょうど1つの Change に落とす分割で書く。** ログは配分・総額・重みを
 * まとめて1件に持つので、独立した条件を並べると「重みも配分も変わったのに配分しか
 * 出ない」「どちらも変わっていないのに空の行が出る」が静かに起きる。
 *
 * 比率は before/after で桁の表記が揺れる（"0.6" と "0.500000"）。文字列のまま
 * 比べると変わっていない値まで変更として出るので、数値に直してから比べる。
 */
function changesOf(before: ProposalSnapshot, after: ProposalSnapshot): Change[] {
  const changes: Change[] = [];

  const beforeRatios = new Map(before.items.map((i) => [i.github_login, toTenths(i.ratio)]));
  const afterRatios = new Map(after.items.map((i) => [i.github_login, toTenths(i.ratio)]));
  // 片方にしか居ないメンバー（分配対象への追加・除外）も拾う
  for (const login of new Set([...beforeRatios.keys(), ...afterRatios.keys()])) {
    const b = beforeRatios.get(login);
    const a = afterRatios.get(login);
    if (b === a) continue;
    changes.push({
      label: login,
      before: b === undefined ? "対象外" : `${formatPercent(b)}%`,
      after: a === undefined ? "対象外" : `${formatPercent(a)}%`,
    });
  }

  if (before.total_amount !== after.total_amount) {
    // 生の "300000.00" を出さない。同じ画面の他の箇所は ¥300,000 で揃っている
    const yen = (v: string | null) =>
      v === null ? "未入力" : `¥${formatAmount(Number(v))}`;
    changes.push({
      label: "報酬総額",
      before: yen(before.total_amount),
      after: yen(after.total_amount),
    });
  }

  for (const [key, label] of [
    ["activity", "活動量の重み"],
    ["speed", "スピードの重み"],
    ["quality", "品質の重み"],
  ] as const) {
    if (before.weights[key] === after.weights[key]) continue;
    changes.push({
      label,
      before: `${before.weights[key]}%`,
      after: `${after.weights[key]}%`,
    });
  }

  return changes;
}

/**
 * 編集履歴のタイムライン（画面7「誰がいつ何を変更したか・その理由を全員に公開」）。
 *
 * 承認制は過剰設計として採らず、**全員に公開されること自体**を不正操作への抑止に
 * している（docs/screen_design.md 画面7）。#100 で受け入れた「ダミーの案を作れば
 * スコアは見られる」という制約も、この公開性が担保になっている。だから畳まず、
 * 誰にでも見える場所に置く。
 */
export function EditHistoryTimeline({ logs }: Props) {
  return (
    <Card title="編集履歴">
      <p className={styles.lead}>
        この案への変更はすべて記録され、チームの全員が見られます。
      </p>

      {logs.length === 0 ? (
        <p className={styles.empty}>まだ調整はありません。</p>
      ) : (
        <ol className={styles.list}>
          {logs.map((log) => {
            const changes = changesOf(log.before_items, log.after_items);
            return (
              <li key={log.id} className={styles.item}>
                <div className={styles.head}>
                  <Avatar
                    login={log.edited_by_github_login ?? "ghost"}
                    url={log.edited_by_avatar_url}
                    size={22}
                  />
                  <span className={`num ${styles.editor}`}>
                    {log.edited_by_github_login ?? "（退会済み）"}
                  </span>
                  <span className={`num ${styles.at}`}>
                    {new Date(log.created_at).toLocaleString("ja-JP")}
                  </span>
                </div>

                <p className={styles.reason}>{log.reason}</p>

                {changes.length > 0 && (
                  <ul className={styles.changes}>
                    {changes.map((c) => (
                      <li key={c.label} className={styles.change}>
                        <span className={`num ${styles.changeLabel}`}>{c.label}</span>
                        <span className={`num ${styles.from}`}>{c.before}</span>
                        <span className={styles.arrow} aria-label="から">
                          →
                        </span>
                        <span className={`num ${styles.to}`}>{c.after}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
