# Vallog — データモデル設計

> カラムの詳細・DDLはAlembicのマイグレーションファイルで管理する。
> このドキュメントはエンティティ間の関係性と設計の意図を記録する概念設計書。

---

## 設計方針

### データ更新方式と保持方針

「オンデマンド」＝ **リアルタイム更新（WebSocket）をしない** という意味であり、キャッシュの有無とは別の話。

| 軸 | 方針 |
|---|---|
| 更新タイミング | リクエスト時（ページリロード）に最新データを取得して表示。WebSocketは不採用 |
| GitHubデータの保持 | DBにキャッシュとして保存する |
| スコアの保持 | DBには保存しない。キャッシュ済みGitHubデータから都度計算 |
| 計算済みスコアの保存 | ❌ 不採用。「なぜそのスコアか」の根拠を隠してしまう |

**GitHubデータをキャッシュする理由**: PR・Issue・レビューなど複数エンドポイントを叩くため、1回のダッシュボード表示で数十〜数百リクエストになりえる。APIレート制限（認証済み: 5,000 req/h）はMVP段階でも超える可能性がある。

**スコアをキャッシュしない理由**: GitHubキャッシュから直接計算できるため保存不要。計算ロジックが変わっても再計算コストが発生しない。

---

## エンティティ一覧

| エンティティ | 役割 |
|---|---|
| users | Vallogアカウント（GitHub OAuthで作成） |
| projects | Vallogプロジェクト（GitHubリポジトリに紐づく） |
| project_members | ユーザーとプロジェクトの多対多を解消する中間テーブル |
| invitation_links | 招待リンク |
| github_pull_requests | GitHubキャッシュ: PRの生データ |
| github_issues | GitHubキャッシュ: Issueの生データ |
| github_issue_assignees | github_issuesとGitHubユーザーの多対多（複数アサイン対応） |
| github_reviews | GitHubキャッシュ: レビューの生データ |
| distribution_proposals | 分配シミュレーション案 |
| distribution_items | 分配案のメンバー別配分値 |
| distribution_edit_logs | 分配案の編集履歴（透明性の担保） |
| contribution_summaries | LLMが生成したメンバー貢献サマリーのキャッシュ（Tier 2） |
| pr_summaries | LLMが生成したPR単位サマリーのキャッシュ（Tier 1） |
| summary_jobs | サマリー生成のバックグラウンドジョブ（状態・進捗） |

---

## エンティティ関係図

```
users
  │
  ├── project_members ── projects
  │                          │
  │                          ├── invitation_links
  │                          │
  │                          ├── github_pull_requests
  │                          ├── github_issues ── github_issue_assignees
  │                          ├── github_reviews
  │                          │
  │                          ├── distribution_proposals
  │                          │         ├── distribution_items
  │                          │         └── distribution_edit_logs
  │                          │
  │                          ├── contribution_summaries
  │                          ├── pr_summaries
  │                          └── summary_jobs
  │
  └── distribution_edit_logs（edited_by）
```

> GitHub OAuth App の資格情報（client_id / client_secret）はDBに持たず、環境変数で設定する

---

## 設計上の重要な判断

### github_login を user_id の代わりに使う

`distribution_items` と `contribution_summaries` はGitHubのコントリビューター単位で管理する。プロジェクト登録時点でコントリビューター全員がVallogアカウントを持っているとは限らないため、`users.id` への外部キーを持つと未登録メンバーを扱えなくなる。

### カテゴリ重みを projects と distribution_proposals の両方に持つ

`projects` にはデフォルト重みを持つ。`distribution_proposals` にも重みカラムを持ち、案ごとに異なる重みで比較できるようにする。分配シミュレーション画面（画面7）の「重みの調整・複数案を比較」というユースケースに対応するため。

### distribution_edit_logs はJSONBスナップショット

変更前後の `distribution_items` の状態をまるごとJSONBで保存する。カラムごとの差分ログよりフロント側でタイムライン表示を組みやすい。`reason`（調整理由）フィールドも持ち、UI側で入力必須とする。定性的な貢献の反映根拠はこのテキストで担保する。

### GitHubキャッシュの更新戦略はTTLベース

`fetched_at` を見てTTLが切れていたらリロード時に再取得する。リロード時に最新データが見えれば十分なユースケースのため。

複数ユーザーが同時にリロードした際のスタンピード対策として、`projects`テーブルに`github_syncing`フラグを持ち、`SELECT FOR UPDATE`で原子的にロックを取る。取得中の場合は古いキャッシュをそのまま返す。

### usersテーブルにgithub_access_tokenを持つ

GitHub OAuthで取得したアクセストークンをDBに暗号化して保存する。VallogのJWT（アクセストークン: メモリ保持 / リフレッシュトークン: HttpOnly Cookie）とは別物。TTLキャッシュ再取得時にこのトークンを使用してGitHub APIを呼ぶ。

### invitation_linksの有効期限は7日間・使用回数無制限

`expires_at`（作成から7日後）を持つ。同じリンクをチームメンバー全員が使い回せる。招待リンク経由でログインした際、ユーザーのGitHubトークンで`GET /repos/{owner}/{repo}`を呼びアクセス権を確認する。privateリポジトリの場合は権限なしユーザーの参加を拒否する。

### 認可設計: 全メンバー同等権限

OwnerとMemberのロール区別なし。プロジェクトメンバーは全員が全操作（ダッシュボード閲覧・分配編集・招待リンク発行・設定変更）を行える。不正操作の抑止は技術的なロールではなく、編集履歴の全員公開による社会的抑止力で担保する。

---

### contribution_summaries / pr_summaries はキャッシュ

LLMの生成コストがかかるため、生成済みのサマリーをDBに保存する。生成に使ったGitHubデータ（title・body・head_sha・レビュー）とプロバイダ/モデル名のハッシュ（`context_hash`）を持ち、変化した場合のみ再生成する。head_shaでdiffの変化を検知するため、キャッシュ判定にGitHub APIを呼ばない。

2層構成でコストを最小化する: `pr_summaries`（Tier 1）はPRごとに1件を生成・キャッシュする。マージ済みPRは内容が不変なので、一度生成したサマリーは再課金されない。`contribution_summaries`（Tier 2）は各Tier 1の要約を入力として生成するため、トークン消費を抑えながら質の高いメンバーサマリーが得られる。生成は `summary_jobs` で管理されるバックグラウンドジョブとして実行し、進捗（done_prs/total_prs）をポーリングで取得する。

---

## 未決事項（Post-MVP検討）

| 項目 | 内容 |
|---|---|
| Discordログ | Post-MVP①でコミュニケーションデータのエンティティ追加 |
