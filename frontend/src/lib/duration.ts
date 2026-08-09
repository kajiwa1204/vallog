/**
 * 経過時間・所要時間の表示用整形。
 *
 * 変化ログ（`初レビューまで 1.4日`）と気にかけること（`33日経過`）で別々に
 * 実装していたが、同じ画面に並ぶ同じ量が別の書式になっていたため1つに寄せた。
 *
 * 日の刻みを一律にしないのは、意味を持つ精度が桁で変わるため。数日のうちは
 * 0.4日の差が「翌日には見てもらえた」という情報になるが、33日経った対象で
 * 0.2日を出しても読み手の判断は変わらない。
 */
const FRACTIONAL_DAYS_LIMIT = 10;

/** 末尾の .0 を落とす。「7.0日」の .0 は精度ではなく雑音 */
function trim(value: string): string {
  return value.replace(/\.0$/, "");
}

export function formatElapsed(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}分`;
  if (hours < 24) return `${trim(hours.toFixed(1))}時間`;
  const days = hours / 24;
  if (days < FRACTIONAL_DAYS_LIMIT) return `${trim(days.toFixed(1))}日`;
  return `${Math.round(days)}日`;
}
