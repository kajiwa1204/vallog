"use client";

import { useEffect, useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Input";
import type { Proposal } from "@/types";
import {
  amountFor,
  equalize,
  formatAmount,
  formatPercent,
  isBalanced,
  isDirty,
  remainingPercent,
  rowsFromItems,
  setRowTenths,
  sumTenths,
  TOTAL_TENTHS,
  type AllocationRow,
} from "./allocation";
import { PanelError } from "./PanelError";
import styles from "./AllocationTable.module.css";

type Props = {
  proposal: Proposal;
  saving: boolean;
  saveError: string | null;
  /** 未確定なのにスコアが非開示＝最終更新から30日を過ぎている（#100） */
  disclosureLapsed: boolean;
  onSaveItems: (rows: AllocationRow[], reason: string) => Promise<boolean>;
  onSaveTotalAmount: (totalAmount: string, reason: string) => Promise<boolean>;
  onFinalize: () => Promise<boolean>;
  onDelete: () => Promise<boolean>;
};

/**
 * 分配比率テーブル（画面7の中心）。
 *
 * 分配額は自動決定しない（docs/scoring_design.md「分配の最終決定は人間」）。スコアは
 * 案を作ったときの出発点になるだけで、以降はメンバーが自由に動かす。ロールによる
 * 編集制限も設けない。抑止は編集履歴の全員公開が担う。
 *
 * **調整には理由の入力を必須にする。** 数字だけが動いた履歴は後から読めず、
 * 「なぜこの配分か」を再構成できない。定性的な貢献を反映する場所でもある。
 */
export function AllocationTable({
  proposal,
  saving,
  saveError,
  disclosureLapsed,
  onSaveItems,
  onSaveTotalAmount,
  onFinalize,
  onDelete,
}: Props) {
  const original = rowsFromItems(proposal.items);
  const [rows, setRows] = useState<AllocationRow[]>(original);
  const [reason, setReason] = useState("");
  const [amountDraft, setAmountDraft] = useState(proposal.total_amount ?? "");
  const [confirmingFinalize, setConfirmingFinalize] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // 案を切り替えたら編集中の値を持ち越さない。残すと、別の案の配分に前の案の
  // 数字が入った状態から編集を始めることになる
  useEffect(() => {
    setRows(rowsFromItems(proposal.items));
    setReason("");
    setAmountDraft(proposal.total_amount ?? "");
    setConfirmingFinalize(false);
    setConfirmingDelete(false);
  }, [proposal.id, proposal.items, proposal.total_amount]);

  const locked = proposal.finalized;

  /**
   * 一度も調整されていない＝配分はスコアをそのままの値。
   *
   * 案の作成時、比率はスコアから算出した値がそのまま入る（services/distribution.py の
   * _score_based_ratios）。既定値は合意されやすいので、放っておくと「スコア＝分配額」が
   * そのまま通り、Goodhartの①ターゲットが折れない。**設計上は「分配の最終決定は人間」
   * だが、人が能動的に動かして初めて成立する**という非対称がここにある。
   *
   * そこで未確定のうちは「これは出発点」と明示し、それでも動かさずに確定したときは
   * その事実を記録として残す。抑止の考え方は既存の「編集履歴を全員に公開する」と同じで、
   * 禁止するのではなく見えるようにする。
   */
  const untouched = proposal.edit_logs.length === 0;
  const total = sumTenths(rows);
  const balanced = isBalanced(rows);
  const dirty = isDirty(rows, original);
  // 理由が空白だけならバックエンドも 422 で弾く。押せるボタンを出さない
  const canSave = dirty && balanced && reason.trim().length > 0;

  const amountChanged = (amountDraft.trim() || null) !== proposal.total_amount;

  return (
    <Card
      title={`分配案: ${proposal.name}`}
      actions={
        <span className={styles.badges}>
          {/* 調整なしで確定した案は、スコアをそのまま採用したという事実が残る。
              確定後は変えられないので、後から読む人にはこれが唯一の手がかりになる */}
          {locked && untouched && <Badge tone="ochre">調整なしで確定</Badge>}
          {locked ? (
            <Badge tone="green">確定済み</Badge>
          ) : (
            <Badge tone="ochre">検討中</Badge>
          )}
        </span>
      }
    >
      <p className={styles.meta}>
        <span>作成 {proposal.created_by_github_login ?? "（退会済み）"}</span>
        <span className="num">
          {new Date(proposal.created_at).toLocaleString("ja-JP")}
        </span>
        {proposal.finalized && proposal.finalized_at && (
          <span>
            確定 {proposal.finalized_by_github_login ?? "（退会済み）"} ・
            <span className="num">
              {" "}
              {new Date(proposal.finalized_at).toLocaleString("ja-JP")}
            </span>
          </span>
        )}
      </p>

      {locked && untouched && (
        <p className={styles.stampNote}>
          この案は一度も調整されずに確定しました。配分はGitHubスコアの計算結果そのままです。
        </p>
      )}

      {!locked && untouched && (
        <p className={styles.startNote}>
          <strong>この配分はスコアをそのまま入れた出発点です。</strong>
          議論して動かしてください。数字に現れない貢献（設計の相談・ドキュメント・運用など）は、下の理由欄に書いて反映できます。
        </p>
      )}

      {!locked && disclosureLapsed && (
        <p className={styles.lapsedNote}>
          この案は<span className="num">30</span>日以上更新されていないため、スコアは非開示に戻っています。配分か重みを保存すると再び表示されます。
        </p>
      )}

      <div className={styles.amountRow}>
        <label className={styles.amountLabel} htmlFor="total-amount">
          報酬総額
        </label>
        <input
          id="total-amount"
          className={`num ${styles.amountInput}`}
          type="number"
          min={0}
          step="0.01"
          inputMode="decimal"
          placeholder="未入力なら割合のみ"
          value={amountDraft}
          disabled={locked || saving}
          onChange={(e) => setAmountDraft(e.target.value)}
        />
        {!locked && amountChanged && (
          <Button
            size="s"
            variant="secondary"
            loading={saving}
            disabled={reason.trim().length === 0}
            onClick={() => onSaveTotalAmount(amountDraft.trim(), reason.trim())}
          >
            総額を保存
          </Button>
        )}
        {!locked && amountChanged && reason.trim().length === 0 && (
          <span className={styles.amountHint}>下の理由欄が必要です</span>
        )}
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">メンバー</th>
            <th scope="col" className={styles.right}>
              配分
            </th>
            <th scope="col" className={styles.right}>
              金額
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const amount = amountFor(amountDraft.trim() || null, row.tenths);
            return (
              <tr key={row.github_login}>
                <th scope="row" className={styles.member}>
                  <Avatar login={row.github_login} url={row.avatar_url} size={24} />
                  <span className="num">{row.github_login}</span>
                </th>
                <td className={styles.right}>
                  {locked ? (
                    <span className="num">{formatPercent(row.tenths)}%</span>
                  ) : (
                    <span className={styles.percentField}>
                      <input
                        className={`num ${styles.percentInput}`}
                        type="number"
                        min={0}
                        max={100}
                        step={0.1}
                        inputMode="decimal"
                        aria-label={`${row.github_login}の配分（%）`}
                        value={formatPercent(row.tenths)}
                        disabled={saving}
                        onChange={(e) =>
                          setRows((current) =>
                            setRowTenths(
                              current,
                              row.github_login,
                              // 千分率の整数に落としてから持つ。パーセントの小数の
                              // まま保持すると合計判定が浮動小数に依存する
                              Math.round(parseFloat(e.target.value) * 10),
                            ),
                          )
                        }
                      />
                      <span className={styles.unit}>%</span>
                    </span>
                  )}
                </td>
                <td className={`num ${styles.right} ${styles.amount}`}>
                  {amount === null ? "—" : `¥${formatAmount(amount)}`}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">合計</th>
            <td
              className={`num ${styles.right} ${balanced ? "" : styles.invalid}`}
            >
              {formatPercent(total)}%
            </td>
            <td className={styles.right} />
          </tr>
        </tfoot>
      </table>

      {!locked && !balanced && (
        <p className={styles.balanceHint}>
          合計を100.0%にしてください（
          <span className="num">
            {total < TOTAL_TENTHS ? `あと ${remainingPercent(rows)}%` : `${formatPercent(total - TOTAL_TENTHS)}% 超過`}
          </span>
          ）。
          <button
            type="button"
            className={styles.link}
            onClick={() => setRows(equalize(rows))}
          >
            均等割りにする
          </button>
        </p>
      )}

      {!locked && (
        <div className={styles.editor}>
          <Textarea
            id="adjust-reason"
            label="調整の理由（必須）"
            hint="全員に公開されます。定性的な貢献（設計の相談・ドキュメント・運用など）を反映した場合はここに書きます。"
            rows={2}
            value={reason}
            disabled={saving}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className={styles.actions}>
            <Button
              disabled={!canSave}
              loading={saving}
              onClick={async () => {
                if (await onSaveItems(rows, reason.trim())) setReason("");
              }}
            >
              配分を保存
            </Button>
            {dirty && (
              <Button
                variant="ghost"
                size="s"
                disabled={saving}
                onClick={() => setRows(original)}
              >
                元に戻す
              </Button>
            )}
          </div>
        </div>
      )}

      {saveError && <PanelError message={saveError} />}

      {!locked && (
        <div className={styles.finalize}>
          {confirmingFinalize ? (
            <>
              <p className={styles.finalizeWarning}>
                確定すると、この案は以降編集できません。スコアの表示も非開示に戻ります（確定した配分は上の表に残ります）。
              </p>
              <div className={styles.actions}>
                <Button loading={saving} disabled={!balanced} onClick={onFinalize}>
                  確定する
                </Button>
                <Button
                  variant="ghost"
                  size="s"
                  disabled={saving}
                  onClick={() => setConfirmingFinalize(false)}
                >
                  やめる
                </Button>
              </div>
            </>
          ) : (
            <Button
              variant="secondary"
              // 編集途中のまま確定すると、画面に出ている数字と保存済みの数字が
              // 違う案が確定される
              disabled={dirty || !balanced}
              onClick={() => setConfirmingFinalize(true)}
            >
              この案で合意を確定する
            </Button>
          )}
          {dirty && (
            <p className={styles.finalizeHint}>
              未保存の調整があります。保存してから確定してください。
            </p>
          )}
        </div>
      )}

      {/* 削除は検討中の案だけ。確定済みは合意の記録なので消せない（APIも409で拒否）。
          「押せないボタンを出さない」ため、確定済みでは導線ごと出さない */}
      {!locked && (
        <div className={styles.danger}>
          {confirmingDelete ? (
            <>
              <p className={styles.dangerWarning}>
                この案と、そこに積まれた調整の履歴を削除します。元に戻せません。
              </p>
              <div className={styles.actions}>
                <Button variant="danger" size="s" loading={saving} onClick={onDelete}>
                  削除する
                </Button>
                <Button
                  variant="ghost"
                  size="s"
                  disabled={saving}
                  onClick={() => setConfirmingDelete(false)}
                >
                  やめる
                </Button>
              </div>
            </>
          ) : (
            <button
              type="button"
              className={styles.deleteLink}
              onClick={() => setConfirmingDelete(true)}
            >
              この案を削除する
            </button>
          )}
        </div>
      )}
    </Card>
  );
}
