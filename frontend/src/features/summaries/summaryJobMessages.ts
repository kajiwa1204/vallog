const PR_REFERENCE = /#\d+/g;

/** バックエンドの開発者向けエラーを、そのまま露出せず行動可能な文言へ変換する。 */
export function summaryJobFailureMessage(error: string | null): string {
  if (!error) return "詳しい原因は取得できませんでした。時間をおいて再生成してください。";

  const lower = error.toLowerCase();
  if (lower.includes("expired") || error.includes("失効")) {
    return "生成処理が時間切れになりました。もう一度生成してください。";
  }
  if (
    lower.includes("api_key") ||
    lower.includes("api key") ||
    error.includes("未設定") ||
    error.includes("認証に失敗")
  ) {
    return "AIサービスの設定を確認できませんでした。管理者に設定の確認を依頼してください。";
  }
  if (lower.includes("rate limit") || error.includes("レート制限")) {
    return "AIサービスの利用上限に達しました。時間をおいて再生成してください。";
  }
  if (lower.includes("timeout") || error.includes("タイムアウト")) {
    return "AIサービスから時間内に応答がありませんでした。時間をおいて再生成してください。";
  }
  if (error.includes("全てのPRサマリー生成に失敗")) {
    const references = error.match(PR_REFERENCE)?.join("、");
    return references
      ? `すべてのPRサマリーを生成できませんでした（${references}）。再生成すると失敗分だけを再試行します。`
      : "すべてのPRサマリーを生成できませんでした。再生成すると失敗分だけを再試行します。";
  }

  return "生成処理中にエラーが発生しました。時間をおいて再生成してください。";
}
