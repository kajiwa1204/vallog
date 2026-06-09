import { type HTMLAttributes, type ReactNode } from "react";
import styles from "./Card.module.css";

type Props = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  title?: ReactNode;
  actions?: ReactNode;
  padded?: boolean;
};

export function Card({ title, actions, padded = true, className, children, ...rest }: Props) {
  return (
    <div className={[styles.card, className].filter(Boolean).join(" ")} {...rest}>
      {(title || actions) && (
        <div className={styles.header}>
          <div className={styles.title}>{title}</div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </div>
      )}
      <div className={padded ? styles.body : undefined}>{children}</div>
    </div>
  );
}
