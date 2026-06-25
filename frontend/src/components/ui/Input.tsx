import { InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import styles from "./Input.module.css";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  hint?: string;
};

export function Input({ label, hint, id, className, ...rest }: InputProps) {
  const input = (
    <input
      id={id}
      className={[styles.input, className].filter(Boolean).join(" ")}
      {...rest}
    />
  );
  if (!label) return input;
  return (
    <label className={styles.field} htmlFor={id}>
      <span className={styles.label}>{label}</span>
      {input}
      {hint && <span className={styles.hint}>{hint}</span>}
    </label>
  );
}

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  hint?: string;
};

export function Textarea({ label, hint, id, className, ...rest }: TextareaProps) {
  const textarea = (
    <textarea
      id={id}
      className={[styles.input, styles.textarea, className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    />
  );
  if (!label) return textarea;
  return (
    <label className={styles.field} htmlFor={id}>
      <span className={styles.label}>{label}</span>
      {textarea}
      {hint && <span className={styles.hint}>{hint}</span>}
    </label>
  );
}
