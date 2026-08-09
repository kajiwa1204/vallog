"use client";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { formatElapsed } from "@/lib/duration";
import type { Attention } from "@/types";
import styles from "./NeedsAttention.module.css";

type Row = {
  key: string;
  number: number;
  title: string;
  html_url: string;
  who: string;
  elapsed: number;
  tone: "ochre" | "neutral" | "red";
  toneLabel: string;
  kind: "review" | "changes" | "stalled" | "draft";
  mine: boolean;
};

type Group = {
  key: string;
  heading: string;
  rows: Row[];
};

/**
 * 気にかけること（attention）。止まっているものだけを集める。
 *
 * ここに並ぶのは誰かの評価ではなく、チームが次に手を付ける先。件数が多いことは
 * 個人の落ち度を意味しない（docs/screen_design.md 画面4）。
 *
 * 全員分をフラットに並べると「誰にとっての情報か」が読み取れず、行動に変換されない。
 * ログイン中のユーザーから見て「次に動かせるのは誰か」で畳み、動かせるものから順に出す。
 * 自分が関わるものでも、レビュー待ちの自分のPRは「あなたの番」に入れない（動かせるのは
 * レビュアーのため）。群の中の並びは経過時間の降順のまま（一番古いものから手を付ける、
 * という意味を保つ）。
 */
export function NeedsAttention({
  attention,
  me,
}: {
  attention: Attention;
  me: string | null;
}) {
  const rows: Row[] = [
    ...attention.review_wanted.map((pr) => ({
      key: `review:${pr.number}`,
      number: pr.number,
      title: pr.title,
      html_url: pr.html_url,
      who: pr.author_login,
      elapsed: pr.waiting_hours,
      tone: "ochre" as const,
      toneLabel: "レビュー待ち",
      kind: "review" as const,
      mine: pr.author_login === me,
    })),
    ...attention.changes_requested.map((pr) => ({
      key: `changes:${pr.number}`,
      number: pr.number,
      title: pr.title,
      html_url: pr.html_url,
      who: pr.author_login,
      elapsed: pr.waiting_hours,
      tone: "ochre" as const,
      toneLabel: "修正待ち",
      kind: "changes" as const,
      mine: pr.author_login === me,
    })),
    ...attention.stalled_issues.map((issue) => ({
      key: `stalled:${issue.number}:${issue.assignee_login}`,
      number: issue.number,
      title: issue.title,
      html_url: issue.html_url,
      who: issue.assignee_login,
      elapsed: issue.stalled_hours,
      tone: "red" as const,
      toneLabel: "担当のまま停滞",
      kind: "stalled" as const,
      mine: issue.assignee_login === me,
    })),
    ...attention.drafts.map((pr) => ({
      key: `draft:${pr.number}`,
      number: pr.number,
      title: pr.title,
      html_url: pr.html_url,
      who: pr.author_login,
      elapsed: pr.waiting_hours,
      tone: "neutral" as const,
      toneLabel: "draft",
      kind: "draft" as const,
      mine: pr.author_login === me,
    })),
  ];

  // 認証確定前は誰の画面か決まらないので、畳まずそのまま出す
  const groups: Group[] =
    me === null
      ? [{ key: "all", heading: "", rows }]
      : [
          // 順序は「やる必要があるか」で決める。この画面が答えると決めた問いが
          // 「自分は今日、何かする必要があるか」なので、義務（自分の番）が先で、
          // 機会（レビューできる）が後。どちらも自分で動かせる点では同じなので、
          // 「動かせる順」では並び順を決められない
          //
          // 「あなたの番」と呼ぶのは自分の手で進められるものだけ。修正待ち（レビューで
          // 指摘を受けた自分のPR）・停滞Issue・draftが該当する
          {
            key: "yours",
            heading: "あなたの番です",
            rows: rows.filter((row) => row.mine && row.kind !== "review"),
          },
          // 他人のレビュー待ちPR。GitHubの requested_reviewers ではないので「依頼された」
          // ではなく「手を挙げられる」。文言もそれ以上を約束しない
          {
            key: "reviewable",
            heading: "あなたがレビューできます",
            rows: rows.filter((row) => row.kind === "review" && !row.mine),
          },
          // 自分のPRのレビュー待ちは別に置く。動かせるのはレビュアーであって、作者にできるのは
          // 声をかけることだけ。「あなたの番」に混ぜると、他人が着手していないことを
          // 自分の停滞として突きつけることになる
          {
            key: "waiting",
            heading: "あなたのPRが待っています",
            rows: rows.filter((row) => row.mine && row.kind === "review"),
          },
          {
            key: "team",
            heading: "チームの状況",
            rows: rows.filter((row) => row.kind !== "review" && !row.mine),
          },
        ].filter((group) => group.rows.length > 0);

  // 自分が動かせるもの（レビューできる／自分の番）。他人待ちの
  // 「あなたのPRが待っています」は自分では動かせないので用事に数えない
  const ownRows = rows.filter(
    (row) => (row.kind === "review" && !row.mine) || (row.mine && row.kind !== "review"),
  );
  const hasOwnBusiness = ownRows.length > 0;

  return (
    <Card
      title="気にかけること"
      actions={
        // 総件数だけだと「8件」が誰の8件か分からない。読み手が知りたいのは
        // 自分の分なので、そちらを先に出す。用事が無いときは .clear が
        // 同じことを言うので件数は出さない
        rows.length > 0 &&
        (hasOwnBusiness ? (
          <span className={`num ${styles.count}`}>
            あなた {ownRows.length} / 全 {rows.length}
          </span>
        ) : null)
      }
    >
      {/* 日常の入口として最初に答えるべきは「自分は今日、何かする必要があるか」
          （docs/screen_design.md 画面4）。答えを副題より前に置く。GitHub側で
          何を見ているかの説明が結論の上に立つと、結論に辿り着くのが遅れる */}
      {rows.length > 0 && me !== null && !hasOwnBusiness && (
        <p className={styles.clear}>いま自分がやることはありません</p>
      )}

      {/* パネル名だけでは中身が推測できない。GitHub側で何を見ているのかを言う
          （群の見出しは行動の言葉なので、外側との段差をここで埋める） */}
      <p className={styles.subtitle}>
        レビュー待ち・修正待ち・担当のまま止まっているIssue
      </p>

      {rows.length === 0 ? (
        <p className={styles.empty}>止まっているものはありません</p>
      ) : (
        <div className={styles.scroll}>
          {groups.map((group) => (
            <section key={group.key}>
              {group.heading && (
                <h3 className={styles.heading}>
                  {group.heading}
                  <span className={`num ${styles.headingCount}`}>
                    {group.rows.length}
                  </span>
                </h3>
              )}
              <ul className={styles.list}>
                {group.rows.map((row) => (
                  <li key={row.key}>
                    <a
                      className={styles.item}
                      href={row.html_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <div className={styles.head}>
                        <Badge tone={row.tone}>{row.toneLabel}</Badge>
                        <span className={`num ${styles.number}`}>
                          #{row.number}
                        </span>
                        <span className={styles.title}>{row.title}</span>
                      </div>
                      <div className={styles.meta}>
                        <span className={`num ${styles.who}`}>{row.who}</span>
                        <span className={`num ${styles.elapsed}`}>
                          {formatElapsed(row.elapsed)}経過
                        </span>
                      </div>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </Card>
  );
}
