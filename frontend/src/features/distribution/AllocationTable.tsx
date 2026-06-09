"use client";

import { useState } from "react";
import styles from "./AllocationTable.module.css";
import type { DistributionItem } from "@/types";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { formatYen } from "@/lib/mockData";

type Props = {
  items: DistributionItem[];
  editable?: boolean;
  onApplyOverride?: (login: string, name: string, amount: number, reason: string) => void;
  onClearOverride?: (login: string) => void;
};

export function AllocationTable({
  items,
  editable = false,
  onApplyOverride,
  onClearOverride,
}: Props) {
  return (
    <div className={styles.table}>
      <div className={[styles.row, styles.head].join(" ")}>
        <span>メンバー</span>
        <span>割合</span>
        <span className={styles.right}>分配額</span>
        {editable && <span className={styles.right}>操作</span>}
      </div>
      {items.map((item) => (
        <AllocationRow
          key={item.login}
          item={item}
          editable={editable}
          onApplyOverride={onApplyOverride}
          onClearOverride={onClearOverride}
        />
      ))}
    </div>
  );
}

function AllocationRow({
  item,
  editable,
  onApplyOverride,
  onClearOverride,
}: {
  item: DistributionItem;
  editable: boolean;
  onApplyOverride?: (login: string, name: string, amount: number, reason: string) => void;
  onClearOverride?: (login: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState<number>(item.manualOverride ?? item.amount);
  const [reason, setReason] = useState("");
  const [showError, setShowError] = useState(false);

  const isOverridden = item.manualOverride !== undefined;
  const displayAmount = item.manualOverride ?? item.amount;
  const diff = isOverridden ? (item.manualOverride ?? 0) - item.amount : 0;

  const startEdit = () => {
    setAmount(displayAmount);
    setReason("");
    setShowError(false);
    setEditing(true);
  };
  const cancelEdit = () => {
    setEditing(false);
    setShowError(false);
  };
  const submitEdit = () => {
    if (!reason.trim()) {
      setShowError(true);
      return;
    }
    onApplyOverride?.(item.login, item.name, amount, reason.trim());
    setEditing(false);
  };
  const handleClear = () => {
    onClearOverride?.(item.login);
  };

  return (
    <>
      <div className={[styles.row, isOverridden ? styles.overridden : ""].join(" ")}>
        <div className={styles.member}>
          <Avatar src={item.avatarUrl} alt={item.name} size={28} />
          <div>
            <div className={styles.name}>{item.name}</div>
            <div className={styles.login}>@{item.login}</div>
          </div>
          {isOverridden && (
            <Badge tone="warn">手動調整</Badge>
          )}
        </div>
        <div className={styles.ratioCell}>
          <div className={styles.ratioBar}>
            <div className={styles.ratioFill} style={{ width: `${item.ratio * 100}%` }} />
          </div>
          <span className={styles.ratioText}>{(item.ratio * 100).toFixed(1)}%</span>
        </div>
        <div className={styles.amountCell}>
          <span className={[styles.right, styles.amount].join(" ")}>{formatYen(displayAmount)}</span>
          {isOverridden && (
            <span className={[styles.diff, diff > 0 ? styles.diffUp : styles.diffDown].join(" ")}>
              {diff > 0 ? "+" : "−"}{formatYen(Math.abs(diff)).replace("¥", "¥")} (元 {formatYen(item.amount)})
            </span>
          )}
        </div>
        {editable && (
          <div className={styles.actions}>
            {editing ? null : isOverridden ? (
              <>
                <Button size="sm" variant="ghost" onClick={handleClear}>
                  リセット
                </Button>
                <Button size="sm" variant="secondary" onClick={startEdit}>
                  再編集
                </Button>
              </>
            ) : (
              <Button size="sm" variant="secondary" onClick={startEdit}>
                編集
              </Button>
            )}
          </div>
        )}
      </div>
      {editing && (
        <div className={styles.editor}>
          <div className={styles.editorRow}>
            <label className={styles.editorField}>
              <span className={styles.editorLabel}>分配額</span>
              <div className={styles.amountInputBox}>
                <span className={styles.yenMark}>¥</span>
                <input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(Number(e.target.value) || 0)}
                  className={styles.amountInput}
                />
              </div>
            </label>
            <label className={styles.editorField}>
              <span className={styles.editorLabel}>
                理由 <span className={styles.required}>必須</span>
              </span>
              <textarea
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                  if (showError && e.target.value.trim()) setShowError(false);
                }}
                placeholder="例: スプリント後半のレビュー対応が多かったため上乗せ"
                rows={2}
                className={[styles.reasonInput, showError ? styles.reasonError : ""].join(" ")}
              />
              {showError && (
                <span className={styles.errorMsg}>理由を入力してください（全員に公開されます）</span>
              )}
            </label>
          </div>
          <div className={styles.editorFoot}>
            <span className={styles.editorHint}>
              💡 編集内容と理由は全員に公開されます。
            </span>
            <div className={styles.editorButtons}>
              <Button size="sm" variant="ghost" onClick={cancelEdit}>キャンセル</Button>
              <Button size="sm" onClick={submitEdit}>調整を反映</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
