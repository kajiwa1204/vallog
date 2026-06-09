import { type ReactNode } from "react";
import styles from "./Badge.module.css";

type Tone = "default" | "accent" | "muted" | "warn";

type Props = {
  children: ReactNode;
  tone?: Tone;
};

export function Badge({ children, tone = "default" }: Props) {
  return <span className={[styles.badge, styles[tone]].join(" ")}>{children}</span>;
}
