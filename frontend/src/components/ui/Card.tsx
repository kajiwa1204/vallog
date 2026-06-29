import { HTMLAttributes, ReactNode } from "react";
import styles from "./Card.module.css";

type Props = HTMLAttributes<HTMLDivElement> & {
  title?: ReactNode;
  actions?: ReactNode;
  padding?: "m" | "none";
};

export function Card({
  title,
  actions,
  padding = "m",
  className,
  children,
  ...rest
}: Props) {
  return (
    <section
      className={[styles.card, className].filter(Boolean).join(" ")}
      {...rest}
    >
      {(title || actions) && (
        <header className={styles.header}>
          {title && <h2 className={styles.title}>{title}</h2>}
          {actions && <div className={styles.actions}>{actions}</div>}
        </header>
      )}
      <div className={padding === "m" ? styles.body : undefined}>{children}</div>
    </section>
  );
}
