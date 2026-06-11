"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Input";
import styles from "./ReasonModal.module.css";

type Props = {
  open: boolean;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (reason: string) => void;
};

// 調整理由の入力を必須とし、編集履歴として全員に公開する（透明性の担保）
export function ReasonModal({ open, saving, error, onClose, onSubmit }: Props) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) setReason("");
  }, [open]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="調整理由を記録する"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            キャンセル
          </Button>
          <Button
            onClick={() => onSubmit(reason)}
            disabled={!reason.trim()}
            loading={saving}
          >
            理由を記録して保存
          </Button>
        </>
      }
    >
      <p className={styles.note}>
        この変更は理由とあわせて編集履歴に記録され、メンバー全員に公開されます。
      </p>
      <Textarea
        label="調整理由（必須）"
        placeholder="例: デザイン作業はGitHubに現れにくいため、◯◯さんの比率を5%上げる"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        autoFocus
      />
      {error && <p className={styles.error}>{error}</p>}
    </Modal>
  );
}
