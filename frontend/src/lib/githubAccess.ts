/**
 * GitHubの `repo` スコープにまつわるユーザー向け説明文。
 *
 * ログイン画面とリポジトリ登録モーダルの両方で同じ説明が要る。片方だけ直して
 * 食い違うのを防ぐため、共通部分はここに集約する。
 */

/**
 * 承認画面の「Full control of private repositories」で驚かせないための先出し。
 * GitHubの承認画面の文言はスコープから自動生成され、こちらでは変更できない。
 */
export const REPO_SCOPE_NOTICE =
  "GitHubの承認画面には「Full control of private repositories」と表示されます。GitHubにprivateを読み取るだけの権限が用意されていないためで、Vallogが読むのはPR・Issue・コミットのみです。リポジトリへの書き込みは一切行いません。";

/**
 * OAuth App access restrictions を有効にしているOrganizationでは、トークンに
 * `repo` があってもorgのprivateリポジトリは一覧に出ない。この場合は再認可しても
 * 直らないため、スコープ判定（private_access）では検知できないことを補う。
 */
export const ORG_RESTRICTION_NOTICE =
  "Organizationのリポジトリは、org側でOAuth Appのアクセスが許可されていないと再認可しても表示されません。その場合はorgの管理者に許可を依頼してください。";

/**
 * privateリポジトリを登録すると、同期したPRタイトルやAI要約がDBに保存され、
 * プロジェクトのメンバーへ配信される。参加時にGitHub側のアクセス権を確認しては
 * いるが、確認は参加時点の1回きりなので、登録前に共有範囲を意識してもらう。
 */
export const PRIVATE_DATA_SHARING_NOTICE =
  "privateリポジトリを登録すると、PRのタイトルやAIによる要約がプロジェクトのメンバーに表示されます。参加にはGitHub側のアクセス権が必要ですが、招待する相手にはご注意ください。";
