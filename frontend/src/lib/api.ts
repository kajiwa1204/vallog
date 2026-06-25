import { API_BASE_URL } from "@/constants";
import type { TokenResponse } from "@/types";

// アクセストークンはXSS耐性のためメモリにのみ保持する
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export class ApiError extends Error {
  status: number;
  // バックエンドが返す機械可読なエラーコード（任意）。将来の細粒度な文言出し分け用。
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

async function rawRequest(path: string, options: RequestOptions): Promise<Response> {
  const { body, headers, ...rest } = options;
  return fetch(`${API_BASE_URL}/api${path}`, {
    ...rest,
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

async function doRefresh(): Promise<TokenResponse | null> {
  const res = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) return null;
  const data = (await res.json()) as TokenResponse;
  accessToken = data.access_token;
  return data;
}

// 複数のリクエストが同時に401になっても、リフレッシュは1回に束ねる
let refreshPromise: Promise<TokenResponse | null> | null = null;

export function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let res = await rawRequest(path, options);

  // アクセストークン未取得・失効時はリフレッシュして一度だけ再試行する
  if (res.status === 401) {
    const session = await refreshSession();
    if (session) {
      res = await rawRequest(path, options);
    }
  }

  if (!res.ok) {
    // detail はバックエンドの英語メッセージ（開発者向け）。ユーザー表示は
    // messageForError() がステータス基準で日本語化するため、ここでは加工しない。
    let detail = `${res.status} ${res.statusText}`;
    let code: string | undefined;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      if (typeof data.code === "string") code = data.code;
    } catch {
      // JSONでないエラーレスポンスはステータス文字列のまま扱う
    }
    throw new ApiError(res.status, detail, code);
  }

  return res.json() as Promise<T>;
}

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

// API/通信エラーをユーザー向けの日本語に変換する。国際化はフロントが担い、
// バックエンドの英語 detail はユーザーには出さない（ログ・開発者向けに留める）。
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

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "DELETE" }),
};
