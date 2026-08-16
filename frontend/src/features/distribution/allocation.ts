// 分配比率の編集ロジック（Reactに依存しない純粋関数）。
//
// フロントにテストランナーが無い（#36）ので、**壊れた状態を表現できない形**に寄せてある。
// 中心にあるのが下の「千分率の整数」で、これが無いと合計判定が浮動小数に依存する。

import type { DistributionItem } from "@/types";

/**
 * 編集中の比率は「千分率の整数」（0〜1000）で持つ。
 *
 * 画面の入力刻みは0.1%なので、パーセントの小数1桁を number のまま足すと
 * `50.1 + 24.9 + 25.0 !== 100` が普通に起きる。合計100%に見えているのに保存ボタンが
 * 出ない、という原因の説明できない状態がこれで作れてしまう。
 *
 * 整数で持てば合計判定は `sum === 1000` の厳密比較になり、送信時の
 * `(tenths / 1000).toFixed(6)` も合計がちょうど 1.000000 になる。**丸め誤差を
 * 許容範囲で吸収するのではなく、そもそも発生させない。**
 */
export const TOTAL_TENTHS = 1000;

export type AllocationRow = {
  github_login: string;
  avatar_url: string | null;
  // 0〜1000（= 0.0%〜100.0%）
  tenths: number;
};

/** APIの比率（"0.500000"）を千分率の整数にする。 */
export function toTenths(ratio: string): number {
  return clampTenths(Math.round(Number(ratio) * TOTAL_TENTHS));
}

/** 千分率の整数をAPIに送る比率文字列にする。合計1000なら比率の合計は 1.000000 になる。 */
export function toRatioString(tenths: number): string {
  return (tenths / TOTAL_TENTHS).toFixed(6);
}

export function clampTenths(tenths: number): number {
  if (!Number.isFinite(tenths)) return 0;
  return Math.min(TOTAL_TENTHS, Math.max(0, Math.round(tenths)));
}

/** 表示用のパーセント（小数1桁）。 */
export function formatPercent(tenths: number): string {
  return (tenths / 10).toFixed(1);
}

export function rowsFromItems(items: DistributionItem[]): AllocationRow[] {
  return items.map((item) => ({
    github_login: item.github_login,
    avatar_url: item.avatar_url,
    tenths: toTenths(item.ratio),
  }));
}

export function sumTenths(rows: AllocationRow[]): number {
  return rows.reduce((total, row) => total + row.tenths, 0);
}

/** 保存してよい状態か。合計がちょうど100.0%であることだけを条件にする。 */
export function isBalanced(rows: AllocationRow[]): boolean {
  return rows.length > 0 && sumTenths(rows) === TOTAL_TENTHS;
}

/**
 * 合計100.0%まであといくつか（正なら足りない・負なら超過）。パーセント表示用。
 *
 * バックエンドは 0.5%ポイントの許容誤差を持つが、それはフロントの丸め由来のズレを
 * 吸収する保険であって入力の許容範囲ではない。常用すると「合計99.7%の案」が確定でき、
 * 分配の合計が報酬総額に一致しなくなる。画面はちょうど100.0%だけを通す。
 */
export function remainingPercent(rows: AllocationRow[]): string {
  return formatPercent(TOTAL_TENTHS - sumTenths(rows));
}

export function setRowTenths(
  rows: AllocationRow[],
  login: string,
  tenths: number,
): AllocationRow[] {
  return rows.map((row) =>
    row.github_login === login ? { ...row, tenths: clampTenths(tenths) } : row,
  );
}

/**
 * 端数を先頭の行に寄せて合計をちょうど1000にする均等割り。
 *
 * 3人なら 333 + 333 + 334。「均等にする」を押した結果が合計99.9%で保存できない、
 * という状態を作らないため、丸めの余りを捨てずに配る。
 */
export function equalize(rows: AllocationRow[]): AllocationRow[] {
  if (rows.length === 0) return rows;
  const base = Math.floor(TOTAL_TENTHS / rows.length);
  const remainder = TOTAL_TENTHS - base * rows.length;
  return rows.map((row, i) => ({ ...row, tenths: base + (i < remainder ? 1 : 0) }));
}

/**
 * 報酬総額を比率で按分した金額。総額が未入力なら金額は出さない（比率のみ表示）。
 *
 * バックエンドの services/distribution.py amount_for() と同じ計算だが、**保存前の
 * 編集中の値**にも金額を出すためにフロントでも計算する。丸めは同じく小数第2位まで。
 */
export function amountFor(totalAmount: string | null, tenths: number): number | null {
  if (totalAmount === null || totalAmount.trim() === "") return null;
  const total = Number(totalAmount);
  if (!Number.isFinite(total)) return null;
  return Math.round(total * (tenths / TOTAL_TENTHS) * 100) / 100;
}

export function formatAmount(amount: number | null): string | null {
  if (amount === null) return null;
  return amount.toLocaleString("ja-JP", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

/**
 * 編集前と比べて配分が変わったか。
 *
 * 変わっていないのに理由を書かせて保存させると、編集履歴に中身の無いログが積まれる。
 * 履歴は全員に公開されて抑止力になっているので、実質の変更が無いログで薄めない。
 */
export function isDirty(rows: AllocationRow[], original: AllocationRow[]): boolean {
  if (rows.length !== original.length) return true;
  const before = new Map(original.map((row) => [row.github_login, row.tenths]));
  return rows.some((row) => before.get(row.github_login) !== row.tenths);
}
