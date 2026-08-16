"use client";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import styles from "./CreateProposalDialog.module.css";

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  creating: boolean;
};

/**
 * 分配案を作る前の確認（#100）。
 *
 * このボタンは**チーム全員に対してスコアを開示する**というチーム規模の副作用を持つ。
 * #100 は「ダミーの案を作ればスコアは見られる」制約を許容したうえで、`created_by` が
 * 記録され編集履歴が公開されることによる社会的抑止で担保するとしている。
 *
 * その抑止は「**見えるかたちで意図的な行為をする必要がある**」ことが前提なので、
 * 押した本人にその意味が見えていなければ成立しない。ボタンが黙って開示スイッチを
 * 兼ねている状態は、抑止の根拠そのものを欠いている。
 *
 * すでにスコアが開示されているとき（未確定の案が他にある）は出さない。開示状態は
 * 変わらないので、警告の中身が事実に反するうえ、ただの摩擦になる。
 */
export function CreateProposalDialog({ open, onClose, onConfirm, creating }: Props) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="分配案を作成します"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={creating}>
            やめる
          </Button>
          <Button onClick={onConfirm} loading={creating}>
            作成する
          </Button>
        </>
      }
    >
      <p className={styles.lead}>
        作成すると、<strong>チーム全員にスコアが表示されます。</strong>
      </p>
      <p className={styles.body}>
        スコアは分配を話し合うための材料なので、この画面で分配を検討している間だけ表示します。
      </p>
      <ul className={styles.notes}>
        <li>作成した人の名前は、以後の編集履歴とあわせて全員に見えます。</li>
        <li>案を確定すると、スコアはまた表示されなくなります。</li>
        <li>
          案が<span className="num">30</span>日更新されないときも、表示されなくなります。
        </li>
      </ul>
    </Modal>
  );
}
