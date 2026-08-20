"use client";

import { useEffect, useRef, useState } from "react";
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
  giveRemainderTo,
  formatPercent,
  isBalanced,
  isDirty,
  remainderFor,
  remainingPercent,
  rowsFromItems,
  setRowTenths,
  sumTenths,
  toTenths,
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

  /**
   * 編集中の入力文字列（github_login → 打っている途中の値）。
   *
   * 入力欄の value を tenths から作り直すと、1文字打つたびに小数1桁へ丸め直される。
   * 「12.5」と打とうとすると `1` → "1.0"、`2` → "1.02"→丸めて"1.0"（握りつぶし）、
   * `5` → "1.05"→"1.1" となり、**数字を打ち込めない**。欄を空にするのも
   * parseFloat("")→NaN→0 で即 0.0 に戻るためできない。
   *
   * 打っている間は入力文字列をそのまま見せ、tenths への変換は裏で行う。フォーカスが
   * 外れた時点で正規化した表示に戻す。
   */
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  /**
   * 配分%の入力欄。**「残りを寄せる」を押した後のフォーカスの行き先**に使う。
   *
   * 押すと合計がちょうど100.0%になり、全行のボタンが同時に消える。押した要素がDOMから
   * 消えるのでフォーカスが <body> に落ち、キーボード操作だと Tab 順の先頭（サイドバー）
   * まで戻される。同じ行の入力欄へ移せば、作業位置も、値が変わったことも保たれる。
   */
  const percentInputs = useRef<Record<string, HTMLInputElement | null>>({});

  const onPercentChange = (login: string, raw: string) => {
    // 空欄や "12." のような途中の文字列は数値にできない。0扱いにせず値を据え置く
    // （0にすると、消して打ち直すたびに合計が崩れて赤くなる）
    const parsed = parseFloat(raw);
    if (Number.isNaN(parsed)) {
      setDrafts((current) => ({ ...current, [login]: raw }));
      return;
    }
    // 範囲外は欄の表示ごと丸める。tenths だけ丸めると「−5 と出ているのに 0 として
    // 計算されている」状態が blur するまで続く（type=number の min は入力を止めない）
    const clamped = Math.min(100, Math.max(0, parsed));
    setDrafts((current) => ({
      ...current,
      [login]: clamped === parsed ? raw : String(clamped),
    }));
    setRows((current) => setRowTenths(current, login, Math.round(clamped * 10)));
  };

  const commitDraft = (login: string) => {
    setDrafts(({ [login]: _dropped, ...rest }) => rest);
  };

  /**
   * 案を切り替えたら編集中の値を持ち越さない。残すと、別の案の配分に前の案の数字が
   * 入った状態から編集を始めることになる。
   *
   * **依存は proposal.id だけにする。** items / total_amount も見ていたが、保存のたびに
   * setProposal(updated) で参照が変わるので、**総額を保存しただけで未保存の配分編集が
   * 黙って消えていた**（サーバ側の items は変わっていないのにフロントだけが捨てる）。
   * 同じ案の中で配分のリセットが要るのは配分そのものを保存したときだけなので、そこは
   * 保存の成功ハンドラで明示的に行う。
   */
  useEffect(() => {
    setRows(rowsFromItems(proposal.items));
    setReason("");
    setAmountDraft(proposal.total_amount ?? "");
    setConfirmingFinalize(false);
    setConfirmingDelete(false);
    setDrafts({});
    // proposal.id 以外は意図的に依存させない（上のコメント参照）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proposal.id]);

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

  /**
   * 最終更新。作成日時と編集ログの最新の新しいほう（サーバの開示判定と同じ定義）。
   *
   * **カウントダウンは出さない。** 「あと3日でスコアが見えなくなります」と出すと、
   * 議論が止まっているのに案を生かすためだけに触る動機になり、30日ルールが塞いだ穴を
   * 開け直すことになる。ここに出すのは期限ではなく事実で、読み手は自分がどこに居るかを
   * 判断できればよい（edit_logs はサーバが created_at の降順で返す）。
   */
  const lastUpdated = proposal.edit_logs[0]?.created_at ?? proposal.created_at;
  const total = sumTenths(rows);
  const balanced = isBalanced(rows);
  const dirty = isDirty(rows, original);
  // 理由が空白だけならバックエンドも 422 で弾く。押せるボタンを出さない
  const canSave = dirty && balanced && reason.trim().length > 0;

  const amountChanged = (amountDraft.trim() || null) !== proposal.total_amount;
  // サーバが返した配分と金額。行が編集されていなければこちらを表示する
  const savedByLogin = new Map(proposal.items.map((item) => [item.github_login, item]));

  /** 行に出す金額。保存済みならサーバの値、編集中なら保存後の見込み。
   *
   * サーバの値を優先するのは、フロントで計算し直すと合意する金額と記録に残る金額が
   * 食い違うため。編集中の行と、総額を書き換えている間だけは、サーバに存在しない値
   * なので保存後の見込みを出す。 */
  const amountOf = (row: AllocationRow): number | null => {
    const saved = savedByLogin.get(row.github_login);
    const untouchedRow =
      !amountChanged && saved !== undefined && toTenths(saved.ratio) === row.tenths;
    if (untouchedRow) return saved.amount === null ? null : Number(saved.amount);
    return amountFor(amountDraft.trim() || null, row.tenths);
  };

  return (
    <Card
      title={`分配案: ${proposal.name}`}
      actions={
        <span className={styles.badges}>
          {/* 調整なしで確定した案は、スコアをそのまま採用したという事実が残る。
              確定後は変えられないので、後から読む人にはこれが唯一の手がかりになる。
              **警告色にしない。** これは「折れていないことを見えるようにする」施策で
              あって咎めではなく、スコアどおりの分配自体は正当な運用。咎める見た目に
              すると、バッジを避けるためだけに0.1%動かして適当な理由を書く動機が生まれ、
              抑止の土台である編集履歴が中身の無いログで薄まる */}
          {locked && untouched && <Badge tone="neutral">調整なしで確定</Badge>}
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
        {/* 確定済みは確定日時が最終更新そのものなので重ねて出さない */}
        {!locked && (
          <span>
            最終更新{" "}
            <span className="num">
              {new Date(lastUpdated).toLocaleString("ja-JP")}
            </span>
          </span>
        )}
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
          この案は<span className="num">30</span>日以上更新されていません。配分か重みを保存すると、上のスコアがまた表示されます。
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
            // 配分の編集中は押させない。理由欄を両方の操作で共有しているので、
            // 同時に保存できると同じ理由文がどちらの編集ログに乗るかが押した
            // ボタン次第になる。禁止すれば dirty のとき理由は配分の保存に、
            // そうでなければ総額の保存に、一意に紐づく
            disabled={dirty || reason.trim().length === 0}
            onClick={() => onSaveTotalAmount(amountDraft.trim(), reason.trim())}
          >
            総額を保存
          </Button>
        )}
        {!locked && amountChanged && (
          <span className={styles.amountHint}>
            {dirty
              ? "先に配分を保存してください"
              : reason.trim().length === 0
                ? "下の理由欄が必要です"
                : ""}
          </span>
        )}
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">メンバー</th>
            <th scope="col" className={`${styles.right} ${styles.allocCol}`}>
              配分
            </th>
            <th scope="col" className={`${styles.right} ${styles.amountCol}`}>
              金額
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const amount = amountOf(row);
            // この行に寄せれば合計がちょうど100.0%になる差分。合計が合っていれば null
            const remainder = locked ? null : remainderFor(rows, row.github_login);
            return (
              <tr key={row.github_login}>
                <th scope="row">
                  {/* flex はセルではなく内側に当てる。<th> に display:flex を当てると
                      テーブルセルでなくなり行の高さに追従しないため、この列だけ
                      border-bottom が数px上にズレる */}
                  <span className={styles.member}>
                    <Avatar login={row.github_login} url={row.avatar_url} size={24} />
                    <span className="num">{row.github_login}</span>
                  </span>
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
                        ref={(el) => {
                          percentInputs.current[row.github_login] = el;
                        }}
                        aria-label={`${row.github_login}の配分（%）`}
                        // 打っている最中は入力文字列をそのまま出す。tenths から
                        // 作り直すと1文字打つたびに小数1桁へ丸め直され、2文字目
                        // 以降が消えて数字を打ち込めなくなる（"12.5" が "1.1" に）
                        value={drafts[row.github_login] ?? formatPercent(row.tenths)}
                        disabled={saving}
                        onChange={(e) => onPercentChange(row.github_login, e.target.value)}
                        onBlur={() => commitDraft(row.github_login)}
                      />
                      <span className={styles.unit}>%</span>
                      {/* 合計がズレているときだけ出す。押すとこの人に過不足を寄せて
                          ちょうど100.0%になる。他の行には触らない */}
                      {remainder !== null && (
                        <button
                          type="button"
                          className={styles.remainder}
                          disabled={saving}
                          aria-label={`残りの ${formatPercent(Math.abs(remainder))}% を ${row.github_login} に${remainder > 0 ? "足す" : "引く"}`}
                          onClick={() => {
                            setRows((current) =>
                              giveRemainderTo(current, row.github_login),
                            );
                            // 入力中の文字列を消さないと、寄せた値がこの欄だけ
                            // 反映されて見えない
                            setDrafts(({ [row.github_login]: _d, ...rest }) => rest);
                            // このボタンは直後に消える。フォーカスを同じ行に残す
                            percentInputs.current[row.github_login]?.focus();
                          }}
                        >
                          {remainder > 0 ? "+" : "−"}
                          {formatPercent(Math.abs(remainder))}
                        </button>
                      )}
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
            {/* 行と同じ構造（数値ブロック＋別の「%」）にする。連続テキストにすると
                「%」の外側でしか揃わず、桁を縦に読む列で肝心の数値がずれる */}
            <td className={styles.right}>
              <span className={styles.percentField}>
                <span
                  className={`num ${styles.totalValue} ${balanced ? "" : styles.invalid}`}
                >
                  {formatPercent(total)}
                </span>
                <span className={styles.unit}>%</span>
              </span>
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
          ）。表の
          <span className={styles.remainderSample}>
            {total < TOTAL_TENTHS ? "+" : "−"}
            {formatPercent(Math.abs(TOTAL_TENTHS - total))}
          </span>
          を押すと、その人に{total < TOTAL_TENTHS ? "残りを足せます" : "超過分を引けます"}。
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
                if (!(await onSaveItems(rows, reason.trim()))) return;
                // 配分を保存したときだけ編集状態を畳む。effect は案の切り替えしか
                // 見ていないので、ここで明示的に行う
                setReason("");
                setDrafts({});
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
            {/* 「全員を同じ配分にする」という方針の選択。合計のズレを直す訂正
                （行の残りボタン）とは別ものなので、同じ文に並べない */}
            <button
              type="button"
              className={styles.equalize}
              disabled={saving}
              onClick={() => {
                setRows(equalize(rows));
                setDrafts({});
              }}
            >
              全員を均等割りにする
            </button>
          </div>
        </div>
      )}

      {saveError && <PanelError message={saveError} />}

      {!locked && (
        <div className={styles.finalize}>
          {confirmingFinalize ? (
            <>
              <p className={styles.finalizeWarning}>
                確定すると、この案は以降編集できません。スコアも表示されなくなります（確定した配分は上の表に残ります）。
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
