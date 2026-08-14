import { API_BASE_URL } from "@/constants";
import type { TokenResponse } from "@/types";

// アクセストークンはXSS耐性のためメモリにのみ保持する
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
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

// タブ間の直列化。リフレッシュCookieはタブ間で共有されるため、束ねを上の
// タブ内変数だけに閉じると複数タブが同じ旧トークンを送り、サーバの再利用検知が
// 誤爆して全セッションが失効する。navigator.locks はオリジン単位で排他できる。
// リフレッシュトークンは HttpOnly Cookie なので、ロック解放後に投げる
// リクエストにはブラウザが自動で新しいトークンを付ける。
// secure context（https / localhost）が必須。非対応環境ではタブ内の束ねだけに戻る
function withCrossTabLock<T>(fn: () => Promise<T>): Promise<T> {
  if (typeof navigator === "undefined" || !navigator.locks) return fn();
  // lib.dom の LockGrantedCallback<T> は「T を返す関数」型で、コールバックが
  // Promise を返した場合の unwrap が反映されていない（Promise<Promise<T>> になる）。
  // 実行時はロック解放前に解決を待つ仕様なので Promise<T> に潰して扱う
  return navigator.locks.request("vallog:auth-refresh", fn) as unknown as Promise<T>;
}

export function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshPromise) {
    refreshPromise = withCrossTabLock(doRefresh).finally(() => {
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

  // 204 No Content はボディを持たないため res.json() を呼ばない
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
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
