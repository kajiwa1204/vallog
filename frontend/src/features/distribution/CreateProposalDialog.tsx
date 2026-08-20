"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import styles from "./CreateProposalDialog.module.css";

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: (name: string, totalAmount: string) => void;
  creating: boolean;
  /** この作成でスコアが開示状態に変わる（他に検討中の案が無い） */
  willDiscloseScores: boolean;
};

/**
 * 分配案の作成。
 *
 * **名前と報酬総額をここで受け取る。** 自動採番（案1, 案2, …）だと、分配を何度も
 * まわすチームで一覧が「案1〜案27」になり、どれがどの賞金の話だったのか区別が付かない。
 * 分配は「いつの・何に対する」報酬かとセットで意味を持つので、名前は作成時に要る。
 * 総額も同じで、後から編集できるとはいえ、賞金が決まっているから分配案を作るという
 * 順序が普通なので入口で受ける。
 *
 * あわせて、この操作が**チーム全員に対してスコアを開示する**ことも伝える（#100）。
 * #100 は「ダミーの案を作ればスコアは見られる」制約を、created_by が記録され編集履歴が
 * 公開されることによる社会的抑止で担保するとしているが、その抑止は「見えるかたちで
 * 意図的な行為をする必要がある」ことが前提で、押した本人にその意味が見えていなければ
 * 成立しない。すでに開示中なら開示状態は変わらないので、その節だけ出さない。
 */
export function CreateProposalDialog({
  open,
  onClose,
  onConfirm,
  creating,
  willDiscloseScores,
}: Props) {
  const [name, setName] = useState("");
  const [totalAmount, setTotalAmount] = useState("");

  // 閉じたら次に開いたときのために捨てる。残すと、前回入力して中断した名前が
  // 別の分配の案に付く
  useEffect(() => {
    if (!open) {
      setName("");
      setTotalAmount("");
    }
  }, [open]);

  const canCreate = name.trim().length > 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新しい分配案"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={creating}>
            やめる
          </Button>
          <Button
            onClick={() => onConfirm(name.trim(), totalAmount.trim())}
            disabled={!canCreate}
            loading={creating}
          >
            作成する
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <Input
          id="proposal-name"
          label="案の名前（必須）"
          placeholder="例: ハッカソン賞金の分配案"
          hint="あとから一覧で見分けるための名前です。いつの・何に対する分配かが分かる名前にしてください。"
          value={name}
          disabled={creating}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          id="proposal-amount"
          label="報酬総額（任意・円）"
          type="number"
          min={0}
          step="0.01"
          inputMode="decimal"
          placeholder="未入力の場合は割合のみ表示"
          value={totalAmount}
          disabled={creating}
          onChange={(e) => setTotalAmount(e.target.value)}
        />
        <p className={styles.note}>
          現在のスコアにもとづく分配比率が初期値として入ります。そこからチームで調整できます。
        </p>
      </div>

      {willDiscloseScores && (
        <div className={styles.disclosure}>
          <p className={styles.disclosureLead}>
            作成すると、<strong>チーム全員にスコアが表示されます。</strong>
          </p>
          <ul className={styles.notes}>
            <li>作成した人の名前は、以後の編集履歴とあわせて全員に見えます。</li>
            <li>案を確定すると、スコアはまた表示されなくなります。</li>
            <li>
              案が<span className="num">30</span>日更新されないときも、表示されなくなります。
            </li>
          </ul>
        </div>
      )}
    </Modal>
  );
}
