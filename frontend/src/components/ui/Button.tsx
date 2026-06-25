import { ButtonHTMLAttributes } from "react";
import styles from "./Button.module.css";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "m" | "s";
  loading?: boolean;
};

export function Button({
  variant = "primary",
  size = "m",
  loading = false,
  disabled,
  className,
  children,
  ...rest
}: Props) {
  return (
    <button
      className={[styles.button, styles[variant], styles[size], className]
        .filter(Boolean)
        .join(" ")}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <span className={styles.spinner} aria-hidden />}
      {children}
    </button>
  );
}
