import Link from "next/link";
import styles from "./page.module.css";

export default function LoginPage() {
  return (
    <main className={styles.container}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>V</span>
          <span>Vallog</span>
        </div>
        <h1 className={styles.title}>有志開発チームの貢献を、客観データで。</h1>
        <p className={styles.lead}>
          GitHubのIssue・PR・レビューデータをもとに、チームの貢献を可視化し、報酬の分配を支援します。
        </p>
        <Link href="/projects" className={styles.cta}>
          <span className={styles.ctaIcon} aria-hidden>🐙</span>
          GitHubでログイン
        </Link>
        <div className={styles.footnote}>
          ※ プロトタイプ版です。実際のGitHub認証は通らずデモデータが表示されます。
        </div>
      </div>
      <ul className={styles.features}>
        <li>
          <strong>透明性</strong> — GitHubへの直リンクで、根拠を隠さない。
        </li>
        <li>
          <strong>客観性</strong> — 定量データを材料に、チームが合意して決める。
        </li>
        <li>
          <strong>チームの自律</strong> — AIは提案のみ。決定はチームが行う。
        </li>
      </ul>
    </main>
  );
}
