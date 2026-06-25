import { ApiError } from "@/lib/api";

// API/通信エラーをユーザー向けの日本語に変換するプレゼンテーション層。
// 国際化はフロントが担い、バックエンドの英語 detail はユーザーには出さない
// （ログ・開発者向けに留める）。ロケールが増えたらこのモジュールを i18n
// ライブラリ実装に差し替える。

type ErrorMessageOverrides = {
  // ステータスコードごとの上書き文言（ドメイン依存の 404/409/410 などに使う）
  [status: number]: string;
  // 上記に該当しないときの既定文言
  fallback?: string;
};

const GENERIC_MESSAGE = "問題が発生しました。時間をおいて再度お試しください。";
const NETWORK_MESSAGE =
  "ネットワークに接続できませんでした。接続を確認してから再度お試しください。";
const SERVER_MESSAGE =
  "サーバーでエラーが発生しました。時間をおいて再度お試しください。";

// インフラ起因（画面に依らず文言が共通の）ステータスの既定訳。
const DEFAULT_MESSAGES: Record<number, string> = {
  401: "セッションの有効期限が切れました。再度ログインしてください。",
  403: "この操作を行う権限がありません。",
  500: SERVER_MESSAGE,
  502: SERVER_MESSAGE,
  503: "サーバーが混み合っています。時間をおいて再度お試しください。",
  504: SERVER_MESSAGE,
};

export function messageForError(
  error: unknown,
  overrides: ErrorMessageOverrides = {},
): string {
  const fallback = overrides.fallback ?? GENERIC_MESSAGE;
  if (error instanceof ApiError) {
    return overrides[error.status] ?? DEFAULT_MESSAGES[error.status] ?? fallback;
  }
  // fetch はネットワーク到達不能時に TypeError を投げる
  if (error instanceof TypeError) return NETWORK_MESSAGE;
  return fallback;
}
