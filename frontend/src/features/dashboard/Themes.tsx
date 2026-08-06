"use client";

import { Card } from "@/components/ui/Card";
import type { Theme } from "@/types";
import styles from "./Themes.module.css";

// 名前空間ごとの表示上限。全体で8件に切ると、件数の多いワークフロー用ラベル
// （task / priority:*）が上位を占めて、肝心の領域ラベルが押し出される
const VISIBLE_PER_GROUP = 5;

type Group = {
  key: string;
  heading: string | null;
  themes: Theme[];
};

/**
 * 動いている領域（themes）。Issueのラベル集計。
 *
 * SPラベル（SP:1〜）はストーリーポイントであって領域ではないため、
 * バックエンド側で落としてある。
 *
 * ラベルを名前空間（"epic:core1" の epic）で束ねるのは、フラットに件数順で並べると
 * task や priority:* のようなワークフロー用ラベルが上位を占め、「動いている領域」
 * という問いに答えられなくなるため。どの接頭辞が領域かはチームのラベル運用ごとに
 * 違うので、除外リストは持たず束ねるだけにして判断は読み手に委ねる。
 */
function groupByNamespace(themes: Theme[]): Group[] {
  const byNamespace = new Map<string, Theme[]>();
  const ungrouped: Theme[] = [];

  for (const theme of themes) {
    if (theme.namespace === null) {
      ungrouped.push(theme);
      continue;
    }
    const bucket = byNamespace.get(theme.namespace);
    if (bucket) bucket.push(theme);
    else byNamespace.set(theme.namespace, [theme]);
  }

  const totalOf = (list: Theme[]) =>
    list.reduce((sum, t) => sum + t.open_count + t.closed_count, 0);

  const groups: Group[] = [...byNamespace.entries()]
    .map(([namespace, list]) => ({
      key: namespace,
      heading: namespace,
      themes: list,
    }))
    .sort((a, b) => totalOf(b.themes) - totalOf(a.themes));

  // 名前空間を持たないラベルは最後。接頭辞の付いたラベルのほうが領域を表している
  // 可能性が高く、先に読ませたい
  if (ungrouped.length > 0) {
    groups.push({ key: "__other", heading: null, themes: ungrouped });
  }
  return groups;
}

export function Themes({ themes }: { themes: Theme[] }) {
  const groups = groupByNamespace(themes);
  const shown = groups.map((group) => ({
    ...group,
    hidden: Math.max(group.themes.length - VISIBLE_PER_GROUP, 0),
    themes: group.themes.slice(0, VISIBLE_PER_GROUP),
  }));
  // バーの長さは全体の最大値で揃える。群ごとに正規化すると、件数の少ない群の
  // バーが不当に長く見えて群をまたいだ比較ができなくなる
  const max = Math.max(...themes.map((t) => t.open_count + t.closed_count), 1);

  return (
    <Card title="動いている領域">
      {/* 「領域」だけでは何を数えたのか分からない。出所を言う */}
      <p className={styles.subtitle}>Issueに付いたラベルごとの件数</p>

      {shown.length === 0 ? (
        <p className={styles.empty}>
          Issueにラベルが付くと、どの領域が動いているかが出ます
        </p>
      ) : (
        shown.map((group) => (
          <section key={group.key} className={styles.group}>
            {group.heading && (
              <h3 className={`num ${styles.groupHeading}`}>{group.heading}</h3>
            )}
            <ul className={styles.list}>
              {group.themes.map((theme) => {
                const total = theme.open_count + theme.closed_count;
                return (
                  <li key={theme.label} className={styles.row}>
                    <span className={styles.label} title={theme.label}>
                      {/* 群の見出しに接頭辞が出ているので、行では省いて残りだけ見せる */}
                      {theme.namespace
                        ? theme.label.slice(theme.namespace.length + 1)
                        : theme.label}
                    </span>
                    <span className={styles.track}>
                      <span
                        className={styles.bar}
                        style={{ width: `${(total / max) * 100}%` }}
                      >
                        <span
                          className={styles.open}
                          style={{ flexGrow: theme.open_count }}
                        />
                        <span
                          className={styles.closed}
                          style={{ flexGrow: theme.closed_count }}
                        />
                      </span>
                    </span>
                    <span className={`num ${styles.counts}`}>
                      <span className={styles.openCount}>
                        {theme.open_count}
                      </span>
                      <span className={styles.slash}>/</span>
                      {total}
                    </span>
                  </li>
                );
              })}
            </ul>
            {group.hidden > 0 && (
              <p className={`num ${styles.more}`}>ほか{group.hidden}種</p>
            )}
          </section>
        ))
      )}

      {shown.length > 0 && (
        <p className={styles.caption}>
          <span className={styles.swatchOpen} />
          オープン
          <span className={styles.swatchClosed} />
          クローズ
          {/* 活動リズムが直近14日なので、同じ画面で期間を書かないと同じ窓に見える */}
          <span className={styles.period}>全期間</span>
        </p>
      )}
    </Card>
  );
}
