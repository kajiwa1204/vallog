"use client";

import Link from "next/link";
import { Avatar } from "@/components/ui/Avatar";
import type { Member } from "@/types";
import styles from "./MemberSwitcher.module.css";

type Props = {
  projectId: string;
  // null なら顔ぶれを引けなかった。切り替え欄ごと出さない（useMemberDetail 参照）
  members: Member[] | null;
  current: string;
  me: string | null;
  fromDistribution?: boolean;
};

/**
 * 人を切り替える導線。
 *
 * ダッシュボードへ戻ってからチップを選び直す2ステップを畳む。並びは
 * TeamChangeLog の絞り込みチップと同じ規則（自分を先頭に固定、残りは辞書順）にする。
 * 活動量順に並べ替えると、この画面が出さないと決めた序列がここに現れる。
 * 自分の定位置が誰の画面でも先頭なのは序列にならない。
 */
export function MemberSwitcher({
  projectId,
  members,
  current,
  me,
  fromDistribution = false,
}: Props) {
  // 顔ぶれを引けていない、または自分1人しか居ない（＝切り替え先が無い）ときは
  // 何も出さない。切り替え先の無い切り替え欄は、置くだけで「壊れている」に見える
  if (members === null) return null;

  // contributors APIはコミットのある人しか返さないので、レビューだけのメンバーを
  // 開いていると一覧に本人が居ない。いま見ている人は必ず並べる
  const logins = Array.from(
    new Set([...members.map((m) => m.github_login), current]),
  );
  if (logins.length < 2) return null;

  const avatars = new Map(members.map((m) => [m.github_login, m.avatar_url]));

  const ordered =
    me !== null && logins.includes(me)
      ? [me, ...logins.filter((l) => l !== me).sort((a, b) => a.localeCompare(b))]
      : logins.sort((a, b) => a.localeCompare(b));

  return (
    <div className={styles.wrap}>
      <div className={styles.chips} role="group" aria-label="メンバーを切り替える">
        {ordered.map((login) => {
          const content = (
            <>
              <Avatar login={login} url={avatars.get(login)} size={18} />
              <span className={`num ${styles.login}`}>{login}</span>
              {login === me && <span className={styles.mine}>あなた</span>}
            </>
          );
          // いま開いている人はリンクにしない。同じページへのリンクは押しても
          // 何も起きず、キーボード操作では意味のない立ち寄り先になる
          return login === current ? (
            <span
              key={login}
              aria-current="page"
              className={`${styles.chip} ${styles.active}`}
            >
              {content}
            </span>
          ) : (
            <Link
              key={login}
              href={`/projects/${projectId}/members/${encodeURIComponent(login)}${
                fromDistribution ? "?from=distribution" : ""
              }`}
              className={styles.chip}
            >
              {content}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
