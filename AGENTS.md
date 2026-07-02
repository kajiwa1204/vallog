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
- **ユーザー向け文言への翻訳はフロントエンドが担う**。`lib/errorMessages.ts` の `messageForError()` がHTTPステータス基準で日本語化する。バックエンドの英語 `detail` をそのままユーザーに表示しない
- ステータスだけで区別できないドメインエラーは、呼び出し側で `messageForError(e, { 409: "...", fallback: "..." })` のように上書きする
- エラーレスポンスは機械可読な `code` を含む（`{"detail"(英語), "code"}`）。バックエンドは `core/errors.py` の `AppError` / `ErrorCode` で投げ（`HTTPException` は使わない）、フロントは `messageForError(e, { codes: { INVITATION_EXPIRED: "..." } })` で `code` 基準に出し分ける。優先順位は code > status > 既定 > fallback
- `code` は契約。`backend/app/core/errors.py` の `ErrorCode` と `frontend/src/lib/errorMessages.ts` の `ApiErrorCode` を同期させる（値は変更しない）

### フロントエンド
- `features/` は機能（画面）ごとにサブディレクトリを作る（例: `features/dashboard/`）
- 各 `features/xxx/` の中はフラットに置く。ファイルが増えてきたら `hooks/` などのサブディレクトリに分けてよい
- `lib/api.ts` は**トランスポート専任**（fetch・認証ヘッダ付与・トークンリフレッシュ・`ApiError` への正規化）。ユーザー向け文言やi18nなどのプレゼンテーション関心事を持ち込まない
- ユーザー向けの文言（エラーメッセージ等）は `lib/errorMessages.ts` のような専用モジュールに置く。依存方向は presentation → transport の一方向に保つ

### バックエンド
- エンドポイントは `routers/` にモデルごとに配置する
- スキーマ（Pydantic）は `schemas/` で管理する
- `routers/` はリクエスト/レスポンスの変換のみ。ビジネスロジック（条件分岐を伴う判定・集約・複数モデルの操作）を書かない
- `services/` はビジネスロジックのみ。DBアクセスをしない（`repositories/` を呼ぶ）
- `repositories/` はDBアクセスのみ。ビジネスロジックを持たない
- `repositories/` の書き込みメソッドは、単純追加ならORMモデルインスタンス、真のupsertならDTOを受け取る（詳細は `docs/directory_structure.md`「設計上の判断」を参照）
- 複数テーブルへの書き込みは `services/` でトランザクションを明示的に囲む
- 依存方向は `routers → services → repositories`。`routers` から `repositories` を直接呼んでよいのは、**次をすべて満たす参照（GET）のみ**:
  - 単一の `repository` メソッドを1回呼ぶだけ
  - 取得結果をそのまま（または Pydantic 変換のみで）返す
  - リクエスト由来の値による絞り込み（例: ログインユーザー自身のリソースへのスコープ）は許容する
- 上記を1つでも外れたら（条件分岐・所有チェックによる拒否・複数 `repository` 呼び出し・集約・キャッシュ・書き込み）必ず `services/` を経由する

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
| `docs/roadmap.md` | 開発ロードマップ・フェーズ計画（GitHub Projectsと連動） |
