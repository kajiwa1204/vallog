"use client";

/* eslint-disable @next/next/no-img-element */
import styles from "./Avatar.module.css";

type Props = {
  login: string;
  url?: string | null;
  size?: number;
};

export function Avatar({ login, url, size = 28 }: Props) {
  // url の読み込みに失敗したら GitHub の identicon にフォールバックする
  const fallback = `https://github.com/${login}.png`;
  return (
    <img
      className={styles.avatar}
      src={url ?? fallback}
      alt={login}
      width={size}
      height={size}
      loading="lazy"
      onError={(e) => {
        if (e.currentTarget.src !== fallback) e.currentTarget.src = fallback;
      }}
    />
  );
}
