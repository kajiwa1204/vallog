"use client";

import { CATEGORIES } from "@/constants";
import type { CategoryWeights } from "@/types";
import styles from "./WeightSliders.module.css";

type Props = {
  value: CategoryWeights;
  onChange: (weights: CategoryWeights) => void;
  disabled?: boolean;
  /** ラジオ・スライダーを id で紐づけるための接頭辞。同一ページに2つ置く場合に要る */
  idPrefix?: string;
};

/** 3カテゴリの重みの合計。100 でなければ保存させない（呼び出し側が判定に使う） */
export function weightTotal(weights: CategoryWeights): number {
  return weights.activity + weights.speed + weights.quality;
}

/**
 * カテゴリ重みの入力（バー＋スライダー＋数値）。
 *
 * プロジェクトのデフォルト重み（画面3）と分配案ごとの重み（画面7）で共有する。
 * 元は features/projects/WeightEditor.tsx の中身だったが、画面7が同じ操作を必要とし、
 * かつ保存の作法だけが違う（画面7は理由の入力が必須）ので、**入力部分だけ**を
 * ここに出した。保存ボタン・確認・API呼び出しは持たない。
 *
 * 重みは値そのものが整数パーセントで、合計100の制約も両画面で同じ。UIを2箇所に
 * 分けると、片方だけ刻みが変わる・片方だけ合計判定が抜ける事故が起きる。
 */
export function WeightSliders({ value, onChange, disabled = false, idPrefix = "weight" }: Props) {
  const set = (key: keyof CategoryWeights, next: number) =>
    onChange({ ...value, [key]: Math.min(100, Math.max(0, next)) });

  return (
    <div className={styles.wrap}>
      <div className={styles.bar}>
        {CATEGORIES.map((c) => (
          <span
            key={c.key}
            className={styles.barSegment}
            style={{ flexGrow: value[c.key], background: c.color }}
          >
            {/* 狭いセグメントに文字を入れると潰れて読めないので、一定幅から出す */}
            {value[c.key] >= 12 && (
              <span className={`num ${styles.barLabel}`}>{value[c.key]}%</span>
            )}
          </span>
        ))}
      </div>

      <div className={styles.rows}>
        {CATEGORIES.map((c) => (
          <div key={c.key} className={styles.row}>
            <label className={styles.label} htmlFor={`${idPrefix}-${c.key}`}>
              <span className={styles.swatch} style={{ background: c.color }} />
              {c.label}
            </label>
            <input
              id={`${idPrefix}-${c.key}`}
              className={styles.slider}
              type="range"
              min={0}
              max={100}
              step={5}
              value={value[c.key]}
              disabled={disabled}
              onChange={(e) => set(c.key, parseInt(e.target.value, 10))}
              style={{ accentColor: c.color }}
            />
            <input
              className={`num ${styles.numInput}`}
              type="number"
              min={0}
              max={100}
              value={value[c.key]}
              disabled={disabled}
              aria-label={`${c.label}の重み（%）`}
              onChange={(e) => set(c.key, parseInt(e.target.value, 10) || 0)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
