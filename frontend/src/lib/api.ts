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

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
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
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      // JSONでないエラーレスポンスはステータス文字列のまま扱う
    }
    throw new ApiError(res.status, detail);
  }

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
