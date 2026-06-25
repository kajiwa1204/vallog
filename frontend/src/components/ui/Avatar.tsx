/* eslint-disable @next/next/no-img-element */
import styles from "./Avatar.module.css";

type Props = {
  login: string;
  url?: string | null;
  size?: number;
};

export function Avatar({ login, url, size = 28 }: Props) {
  return (
    <img
      className={styles.avatar}
      src={url ?? `https://github.com/${login}.png`}
      alt={login}
      width={size}
      height={size}
      loading="lazy"
    />
  );
}
