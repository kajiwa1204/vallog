import styles from "./Avatar.module.css";

type Props = {
  src: string;
  alt: string;
  size?: number;
};

export function Avatar({ src, alt, size = 32 }: Props) {
  return (
    <span
      className={styles.avatar}
      style={{ width: size, height: size }}
      aria-label={alt}
      role="img"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} width={size} height={size} />
    </span>
  );
}
