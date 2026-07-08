import { ApiError } from "@/lib/api";

// API/通信エラーをユーザー向けの日本語に変換するプレゼンテーション層。
// 国際化はフロントが担い、バックエンドの英語 detail はユーザーには出さない
// （ログ・開発者向けに留める）。ロケールが増えたらこのモジュールを i18n
// ライブラリ実装に差し替える。

// バックエンドの機械可読なエラーコード。backend/app/core/errors.py の
// ErrorCode と同期させる（値は契約なので変更しない）。
export type ApiErrorCode =
  | "AUTH_NOT_AUTHENTICATED"
  | "AUTH_INVALID_TOKEN"
  | "AUTH_USER_NOT_FOUND"
  | "AUTH_REFRESH_TOKEN_MISSING"
  | "AUTH_TOKEN_REUSE_DETECTED"
  | "PROJECT_NOT_FOUND"
  | "PROJECT_FORBIDDEN"
  | "REPO_ALREADY_REGISTERED"
  | "REPO_NOT_FOUND"
  | "REPO_ACCESS_DENIED"
  | "INVITATION_NOT_FOUND"
  | "INVITATION_EXPIRED"
  | "GITHUB_TIMEOUT"
  | "GITHUB_UNAVAILABLE"
  | "GITHUB_AUTH_FAILED"
  | "GITHUB_FORBIDDEN"
  | "GITHUB_RATE_LIMITED"
  | "GITHUB_TOKEN_EXCHANGE_FAILED"
  | "GITHUB_USER_FETCH_FAILED"
  | "GITHUB_INVALID_RESPONSE";

type ErrorMessageOverrides = {
  // エラーコードごとの上書き文言。同じステータスで意味が分かれる場合に使う
  // （例: 404 の INVITATION_NOT_FOUND と REPO_NOT_FOUND）。status より優先。
  codes?: Partial<Record<ApiErrorCode, string>>;
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
    // 優先順位: code指定 > status指定 > statusの既定訳 > fallback
    const byCode = error.code
      ? overrides.codes?.[error.code as ApiErrorCode]
      : undefined;
    return (
      byCode ??
      overrides[error.status] ??
      DEFAULT_MESSAGES[error.status] ??
      fallback
    );
  }
  // fetch はネットワーク到達不能時に TypeError を投げる
  if (error instanceof TypeError) return NETWORK_MESSAGE;
  return fallback;
}
