import styles from "./CategoryPieChart.module.css";
import type { MemberScore, ScoreCategory } from "@/types";

type Props = {
  scores: MemberScore[];
};

const categories: Array<{ key: ScoreCategory; label: string; color: string; desc: string }> = [
  { key: "issue", label: "Issue", color: "var(--chart-1)", desc: "解決済みIssue" },
  { key: "pr", label: "PR", color: "var(--chart-2)", desc: "マージされたPR" },
  { key: "review", label: "Review", color: "var(--chart-3)", desc: "他メンバーへのレビュー" },
  { key: "tat", label: "TAT", color: "var(--chart-4)", desc: "リードタイム" },
  { key: "sp", label: "SP", color: "var(--chart-5)", desc: "ストーリーポイント" },
];

const polarToCartesian = (cx: number, cy: number, r: number, angle: number) => {
  const rad = ((angle - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
};

const arcPath = (cx: number, cy: number, rOuter: number, rInner: number, start: number, end: number) => {
  const largeArc = end - start > 180 ? 1 : 0;
  const p1 = polarToCartesian(cx, cy, rOuter, start);
  const p2 = polarToCartesian(cx, cy, rOuter, end);
  const p3 = polarToCartesian(cx, cy, rInner, end);
  const p4 = polarToCartesian(cx, cy, rInner, start);
  return [
    `M ${p1.x} ${p1.y}`,
    `A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${p2.x} ${p2.y}`,
    `L ${p3.x} ${p3.y}`,
    `A ${rInner} ${rInner} 0 ${largeArc} 0 ${p4.x} ${p4.y}`,
    "Z",
  ].join(" ");
};

export function CategoryPieChart({ scores }: Props) {
  const totals = categories.map((c) => ({
    ...c,
    value: scores.reduce((acc, s) => acc + s.breakdown[c.key], 0),
  }));
  const grandTotal = totals.reduce((acc, t) => acc + t.value, 0);

  const size = 280;
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = 130;
  const rInner = 80;

  let cursor = 0;

  return (
    <div className={styles.wrapper}>
      <div className={styles.chart}>
        <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label="カテゴリ別スコア内訳">
          {totals.map((t) => {
            const angle = grandTotal > 0 ? (t.value / grandTotal) * 360 : 0;
            const path = arcPath(cx, cy, rOuter, rInner, cursor, cursor + angle);
            cursor += angle;
            return <path key={t.key} d={path} fill={t.color}><title>{`${t.label}: ${t.value} pts`}</title></path>;
          })}
        </svg>
        <div className={styles.centerLabel}>
          <div className={styles.centerValue}>{grandTotal}</div>
          <div className={styles.centerUnit}>pts</div>
        </div>
      </div>
      <ul className={styles.legend}>
        {totals.map((t) => {
          const pct = grandTotal > 0 ? (t.value / grandTotal) * 100 : 0;
          return (
            <li key={t.key} className={styles.legendItem}>
              <span className={styles.legendDot} style={{ backgroundColor: t.color }} />
              <div className={styles.legendBody}>
                <div className={styles.legendHead}>
                  <span className={styles.legendLabel}>{t.label}</span>
                  <span className={styles.legendValue}>
                    {t.value} <span className={styles.legendPct}>({pct.toFixed(1)}%)</span>
                  </span>
                </div>
                <div className={styles.legendDesc}>{t.desc}</div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
