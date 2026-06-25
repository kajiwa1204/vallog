# Vallog — AGENTS.md

有志開発チーム（ハッカソン・副業・学生チームなど）向けの貢献可視化・報酬分配ツール。

- **ビジョン**: 有志開発チームでの新規プロダクト創出を最大化する
- **ミッション**: チーム開発の貢献を客観データで可視化し、正しく報いるインフラを作る

設計書は `docs/` 以下を参照。実装前に必ず確認すること。

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | Next.js (App Router) |
| スタイリング | CSS Modules（Tailwindは不採用） |
| UIコンポーネント | 自前実装 |
| バックエンド | FastAPI |
| ORM / マイグレーション | SQLAlchemy (asyncio) + Alembic |
| DB | PostgreSQL |
| 認証 | GitHub OAuth |
| インフラ | Docker Compose + Cloudflare Tunnel + nginx |

---

## コマンド

> インフラ構成確定後に追記する

---

## ディレクトリ構成

`docs/directory_structure.md` を参照。**ディレクトリ構成を遵守すること**（ファイル名・ファイル数は実装に応じて変えてよい）。

---

## コーディング規約

### 共通
- コメントは「なぜ」が非自明な場合のみ書く。「何をしているか」はコードで表現する

### エラーメッセージと国際化
- **APIエラーメッセージ（`HTTPException` の `detail`）は英語で書く**。これは開発者向け・ログ向けの識別情報であり、契約として安定させる
- **ユーザー向け文言への翻訳はフロントエンドが担う**。`lib/api.ts` の `messageForError()` がHTTPステータス基準で日本語化する。バックエンドの英語 `detail` をそのままユーザーに表示しない
- ステータスだけで区別できないドメインエラーは、呼び出し側で `messageForError(e, { 409: "...", fallback: "..." })` のように上書きする
- 将来さらに細かい出し分けが要る場合は、バックエンドがレスポンスに機械可読な `code` を含め、フロントは `ApiError.code` で引く（ステータス=ざっくり分類、`code`=細粒度、文言=フロントが翻訳）

### フロントエンド
- `features/` は機能（画面）ごとにサブディレクトリを作る（例: `features/dashboard/`）
- 各 `features/xxx/` の中はフラットに置く。ファイルが増えてきたら `hooks/` などのサブディレクトリに分けてよい

### バックエンド
- エンドポイントは `routers/` にモデルごとに配置する
- スキーマ（Pydantic）は `schemas/` で管理する
- `routers/` はリクエスト/レスポンスの変換のみ。ビジネスロジックを書かない
- `services/` はビジネスロジックのみ。DBアクセスをしない（`repositories/` を呼ぶ）
- `repositories/` はDBアクセスのみ。ビジネスロジックを持たない
- 複数テーブルへの書き込みは `services/` でトランザクションを明示的に囲む

---

## 設計書

| ドキュメント | 内容 |
|---|---|
| `docs/product_overview.md` | ビジョン・ミッション・MVPスコープ |
| `docs/scoring_design.md` | スコアリング設計・分配シミュレーション |
| `docs/screen_design.md` | 画面設計・機能要件 |
| `docs/tech_stack.md` | 技術スタック・インフラ |
| `docs/data_model.md` | エンティティ設計・設計の意図 |
| `docs/directory_structure.md` | ディレクトリ構成 |
