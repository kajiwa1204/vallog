import { ReactNode } from "react";
import styles from "./Badge.module.css";

type Props = {
  children: ReactNode;
  tone?: "neutral" | "green" | "ochre" | "slate" | "red";
};

export function Badge({ children, tone = "neutral" }: Props) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>;
}
