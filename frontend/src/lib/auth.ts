import { API_BASE_URL } from "@/constants";

// OAuth でサイト外（GitHub）へ遷移するため、復帰先はメモリではなく
// sessionStorage に退避する（タブ単位で分離され、閉じれば消える）
const RETURN_TO_KEY = "vallog:return_to";

export function startGitHubLogin(returnTo?: string) {
  if (returnTo) {
    sessionStorage.setItem(RETURN_TO_KEY, returnTo);
  } else {
    sessionStorage.removeItem(RETURN_TO_KEY);
  }
  window.location.href = `${API_BASE_URL}/api/auth/github`;
}

export function consumeReturnTo(): string | null {
  const value = sessionStorage.getItem(RETURN_TO_KEY);
  sessionStorage.removeItem(RETURN_TO_KEY);
  // open redirect 防止: アプリ内の絶対パスのみ許可する
  if (value && value.startsWith("/") && !value.startsWith("//")) return value;
  return null;
}
