import type { CategoryKey } from "@/types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

// スコアカテゴリの表示情報。色はデザイントークン（globals.css）と対応
export const CATEGORIES: {
  key: CategoryKey;
  label: string;
  // 幅の狭い所で使う短縮名。正式名は label 側で、凡例が対応を示す
  short: string;
  color: string;
  tint: string;
}[] = [
  {
    key: "activity",
    label: "GitHub活動量",
    short: "活動量",
    color: "#177245",
    tint: "#e8f3ec",
  },
  {
    key: "speed",
    label: "タスク完了スピード",
    short: "スピード",
    color: "#c77d1f",
    tint: "#f9efe0",
  },
  {
    key: "quality",
    label: "品質・可用性",
    short: "品質",
    color: "#4a6fa5",
    tint: "#e9eff7",
  },
];

export const CATEGORY_MAP = Object.fromEntries(
  CATEGORIES.map((c) => [c.key, c]),
) as Record<CategoryKey, (typeof CATEGORIES)[number]>;
