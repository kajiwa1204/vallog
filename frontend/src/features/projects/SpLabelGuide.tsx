"use client";

import { useState } from "react";
import styles from "./SpLabelGuide.module.css";

const STEPS = [
  {
    title: "GitHubでSPラベルを作成する",
    body: "リポジトリの Issues → Labels → New label から、SP:1 / SP:2 / SP:3 / SP:5 / SP:8 のラベルを作成します。数字はタスクの大きさ（ストーリーポイント）です。",
  },
  {
    title: "Issueにラベルとアサインを設定する",
    body: "タスクのIssueにSPラベルを1つ付け、担当者をアサインします。アサインした時刻が計測の起点になります。",
  },
  {
    title: "PRマージでIssueをクローズする",
    body: "PRの説明に「Closes #123」と書いてマージすると、Issueが自動でクローズされ、アサイン〜クローズの時間で「タスク完了スピード」が計測されます。",
  },
];

// タスク完了スピードの計測にはSPラベル運用が前提（GitHub Projects運用を必須とする）
export function SpLabelGuide() {
  const [open, setOpen] = useState(false);

  return (
    <div className={styles.wrap}>
      <div className={styles.intro}>
        <p className={styles.introText}>
          「タスク完了スピード」の計測には、GitHub IssuesのSPラベル
          （<span className="num">SP:1</span>〜<span className="num">SP:8</span>）
          の運用が必要です。
        </p>
        <button className={styles.toggle} onClick={() => setOpen(!open)}>
          {open ? "閉じる" : "設定方法を見る"}
        </button>
      </div>

      {open && (
        <ol className={styles.steps}>
          {STEPS.map((step, i) => (
            <li key={step.title} className={styles.step}>
              <span className={`num ${styles.stepNum}`}>{i + 1}</span>
              <div>
                <h4 className={styles.stepTitle}>{step.title}</h4>
                <p className={styles.stepBody}>{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
