import { API_BASE_URL } from "@/constants";

// OAuth でサイト外（GitHub）へ遷移するため、復帰先はメモリではなく
// sessionStorage に退避する（タブ単位で分離され、閉じれば消える）
const RETURN_TO_KEY = "vallog:return_to";

export function startGitHubLogin(returnTo?: string) {
  // ストレージ無効環境（Cookieブロック設定・プライベートモード等）では
  // 復帰先の保持を諦めるだけにして、ログイン遷移自体は止めない
  try {
    if (returnTo) {
      sessionStorage.setItem(RETURN_TO_KEY, returnTo);
    } else {
      sessionStorage.removeItem(RETURN_TO_KEY);
    }
  } catch {
    // 復帰先が失われても既定の遷移先（/projects）で継続できる
  }
  window.location.href = `${API_BASE_URL}/api/auth/github`;
}

export function consumeReturnTo(): string | null {
  try {
    const value = sessionStorage.getItem(RETURN_TO_KEY);
    sessionStorage.removeItem(RETURN_TO_KEY);
    // open redirect 防止: アプリ内の絶対パスのみ許可する
    if (value && value.startsWith("/") && !value.startsWith("//")) return value;
    return null;
  } catch {
    return null;
  }
}
