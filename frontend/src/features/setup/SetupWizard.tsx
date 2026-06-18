"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import styles from "./SetupWizard.module.css";

type Props = {
  callbackUrl: string;
  onComplete: () => void;
};

export function SetupWizard({ callbackUrl, onComplete }: Props) {
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const [copiedField, setCopiedField] = useState<string | null>(null);

  const copy = async (text: string, key: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedField(key);
    setTimeout(() => setCopiedField(null), 1500);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!clientId.trim() || !clientSecret.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/setup/github", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId.trim(), client_secret: clientSecret.trim() }),
      });
      if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`;
        try {
          const data = await res.json();
          if (typeof data.detail === "string") detail = data.detail;
        } catch {
          // JSONでないエラーはステータス文字列のまま
        }
        throw new Error(detail);
      }
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "不明なエラーが発生しました");
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className={styles.card}>
        <div className={styles.successIcon} aria-hidden>✓</div>
        <h2 className={styles.title}>設定が完了しました</h2>
        <p className={styles.desc}>GitHub OAuth Appの設定が保存されました。ログインできます。</p>
        <Button onClick={onComplete} className={styles.fullWidth}>
          ログイン画面へ
        </Button>
      </div>
    );
  }

  const homepageUrl =
    typeof window !== "undefined" ? window.location.origin : "";

  return (
    <div className={styles.card}>
      <h2 className={styles.title}>セットアップ</h2>
      <p className={styles.desc}>
        VallogはGitHub OAuthを使ってログインします。GitHub OAuth Appを作成し、以下の情報を入力してください。
      </p>

      {/* Step 1: GitHub OAuth App作成リンク */}
      <section className={styles.step}>
        <div className={styles.stepHeader}>
          <span className={styles.stepNum}>1</span>
          <span className={styles.stepLabel}>GitHub OAuth Appを作成</span>
        </div>
        <a
          href="https://github.com/settings/applications/new"
          target="_blank"
          rel="noopener noreferrer"
          className={styles.externalLink}
        >
          GitHub で OAuth App を作成する ↗
        </a>
      </section>

      {/* Step 2: 入力値の提示 */}
      <section className={styles.step}>
        <div className={styles.stepHeader}>
          <span className={styles.stepNum}>2</span>
          <span className={styles.stepLabel}>以下の値を入力</span>
        </div>
        <div className={styles.fieldGroup}>
          <CopyRow
            label="Application name"
            value="Vallog"
            copied={copiedField === "name"}
            onCopy={() => copy("Vallog", "name")}
          />
          <CopyRow
            label="Homepage URL"
            value={homepageUrl}
            copied={copiedField === "homepage"}
            onCopy={() => copy(homepageUrl, "homepage")}
          />
          <CopyRow
            label="Authorization callback URL"
            value={callbackUrl}
            copied={copiedField === "callback"}
            onCopy={() => copy(callbackUrl, "callback")}
          />
        </div>
      </section>

      {/* Step 3: Client IDとSecretの入力 */}
      <section className={styles.step}>
        <div className={styles.stepHeader}>
          <span className={styles.stepNum}>3</span>
          <span className={styles.stepLabel}>Client IDとClient Secretを貼り付け</span>
        </div>
        <form onSubmit={handleSubmit} className={styles.form}>
          <Input
            label="Client ID"
            id="client-id"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Ov23li..."
            autoComplete="off"
            required
          />
          <Input
            label="Client Secret"
            id="client-secret"
            type="password"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            placeholder="生成したClient Secretを貼り付け"
            autoComplete="off"
            required
          />
          {error && <p className={styles.error}>{error}</p>}
          <Button
            type="submit"
            loading={submitting}
            disabled={!clientId.trim() || !clientSecret.trim()}
            className={styles.fullWidth}
          >
            設定を保存
          </Button>
        </form>
      </section>
    </div>
  );
}

function CopyRow({
  label,
  value,
  copied,
  onCopy,
}: {
  label: string;
  value: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className={styles.copyRow}>
      <span className={styles.copyLabel}>{label}</span>
      <div className={styles.copyValue}>
        <code className={styles.copyCode}>{value}</code>
        <button type="button" className={styles.copyBtn} onClick={onCopy}>
          {copied ? "コピー済み" : "コピー"}
        </button>
      </div>
    </div>
  );
}
