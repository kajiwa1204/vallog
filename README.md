# Vallog

有志開発チーム（ハッカソン・副業・学生チームなど）向けの貢献可視化・報酬分配ツール。

- **ビジョン**: 有志開発チームでの新規プロダクト創出を最大化する
- **ミッション**: チーム開発の貢献を客観データで可視化し、正しく報いるインフラを作る

詳細は [docs/product_overview.md](docs/product_overview.md) を参照。

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | Next.js (App Router) |
| スタイリング | CSS Modules |
| バックエンド | FastAPI |
| ORM / マイグレーション | SQLAlchemy + Alembic |
| DB | PostgreSQL |
| 認証 | GitHub OAuth |
| インフラ | Docker Compose + Cloudflare Tunnel + nginx |

---

## ローカル開発環境

### 前提条件

- Docker / Docker Compose
- Python 3（`.env` 生成スクリプト用。標準ライブラリのみ使用）

Node.js のローカルインストールは不要。フロントエンドの実行もビルドもコンテナ内で行う。

### 1. 環境変数を用意する

```bash
make setup
```

`.env.dev.example` から `.env` を生成し、`ENCRYPTION_KEY`（GitHubアクセストークンの暗号化キー）を自動生成する。あわせて `frontend/node_modules` の生成と Docker イメージのビルドまで行うため、初回は数分かかる。

`node_modules` をローカルに置くのは IDE の型補完のためで、アプリの実行には使わない。

### 2. GitHub OAuth App を登録する

[GitHub Developer settings](https://github.com/settings/developers) で **New OAuth App** を作成する。

| 項目 | 値 |
|---|---|
| Application name | 任意 |
| Homepage URL | `http://localhost:3000` |
| Authorization callback URL | `http://localhost:3000/api/auth/github/callback` |

callback URL の `/api` は Next.js の rewrites（`/api/:path*` → バックエンド）を通すためのもので、省略すると認証が一周しない。

発行された値を `.env` に書く。

```bash
GITHUB_CLIENT_ID=Ov23...
GITHUB_CLIENT_SECRET=...
```

`JWT_SECRET` は dev の既定値のままでも起動する。実運用に近づけるなら `openssl rand -hex 32` の出力に差し替える。

### 3. 起動する

```bash
make dev
```

フォアグラウンドで起動し、http://localhost:3000 で開く。

### 4. マイグレーションを適用する

**別のターミナル**で実行する。

```bash
make migrate
```

初回は必須。テーブルが無い状態ではログイン後の画面がすべて失敗する。

### よく使うコマンド

| コマンド | 内容 |
|---|---|
| `make dev` | 開発環境を起動（フォアグラウンド） |
| `make dev-down` | 開発環境を停止 |
| `make migrate` | マイグレーションを適用 |
| `make migrate-create msg="..."` | マイグレーションを自動生成 |
| `make logs` | ログを追う |
| `make shell-backend` | バックエンドコンテナに入る |
| `make shell-db` | psql を開く |
| `make clean` | コンテナ・ボリューム・イメージを削除（DBの中身も消える） |

`make` 系はすべて `ENV=prod` を付けると本番構成（`docker-compose.yml` + Cloudflare Tunnel）を対象にする。既定は `ENV=dev`。

### テスト

```bash
# バックエンド
make shell-backend
pytest -q

# フロントエンド
cd frontend
pnpm typecheck && pnpm lint && pnpm test
```

---

## ディレクトリ構成

詳細は [docs/directory_structure.md](docs/directory_structure.md) を参照。

```
vallog/
├── backend/          # FastAPI
├── frontend/         # Next.js
├── nginx/            # リバースプロキシ設定
├── docs/             # 設計書
└── .claude/          # Claude Code 設定
```

---

## フロントエンド: コンポーネントの配置ルール

`components/ui/` と `features/` のどちらに置くかは「**画面・機能への依存があるか**」で判断する。

### `src/components/ui/` — 汎用コンポーネント

特定の画面や機能に依存しない、再利用可能なコンポーネント。

```
components/ui/
├── Button.tsx         # どの画面でも使う
├── Modal.tsx
└── Input.tsx
```

**配置基準**: props だけで動作が完結し、プロジェクト固有のロジックを持たないもの。

### `src/features/` — 機能別コンポーネント

特定の画面・機能に紐づくコンポーネント・hooks。

```
features/
├── dashboard/
│   ├── MemberCard.tsx     # ダッシュボード専用
│   └── useDashboard.ts
├── distribution/
│   └── AllocationTable.tsx
└── members/
    └── ScoreBreakdown.tsx
```

**配置基準**: ダッシュボードのメンバーカードやスコア表示など、特定画面の文脈でしか意味をなさないもの。

### `src/hooks/` — 横断 hooks

複数の `features/` をまたいで使う hooks はここに置く。

```
hooks/
└── useAuth.ts    # 認証状態管理（全画面共通）
```

---

## 設計書

| ドキュメント | 内容 |
|---|---|
| [product_overview.md](docs/product_overview.md) | ビジョン・ミッション・MVPスコープ |
| [scoring_design.md](docs/scoring_design.md) | スコアリング設計・分配シミュレーション |
| [screen_design.md](docs/screen_design.md) | 画面設計・機能要件 |
| [tech_stack.md](docs/tech_stack.md) | 技術スタック・インフラ |
| [data_model.md](docs/data_model.md) | エンティティ設計・設計の意図 |
| [directory_structure.md](docs/directory_structure.md) | ディレクトリ構成 |

---

## 開発フロー

### 全体の流れ

```
Issue 作成 → ブランチ作成 → 実装・コミット → PR 作成 → レビュー → マージ
```

### 1. Issue 管理

GitHub Projects を使ってタスクを管理する。

- **親Issue（エピック）**: 機能単位でまとまった作業。着手時に担当者の判断で子Issueに分割してよい
- **子Issue**: 1PR = 1子Issue が目安。作成したら親IssueのBodyに `- [ ] #XX タスク名` 形式で追記するとプログレスバーが自動表示される

Issueテンプレートは `.github/ISSUE_TEMPLATE/` に用意されている。

| テンプレート | 用途 |
|---|---|
| `task.yml` | 通常の実装タスク |
| `feature_request.yml` | 新機能の提案 |
| `bug_report.yml` | バグ報告 |
| `documentation.yml` | ドキュメント作業 |

### 2. ブランチ命名規則

```
<type>/<kebab-case-description>
```

| type | 用途 |
|---|---|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `docs` | ドキュメント |
| `chore` | 設定変更・雑務 |
| `refactor` | リファクタリング |
| `test` | テスト追加・修正 |

Issue と関連する場合は Issue 番号をプレフィックスに付ける。

```
<type>/<issue-number>-<kebab-case-description>
```

例: `feat/42-dashboard-score-chart`、`fix/57-auth-redirect`

Issue と無関係な作業（依頼されていない修正など）はそのまま。

例: `docs/update-data-model`、`chore/update-dependencies`

### 3. コミット

**1コミット = 1つの変更目的。** 機能追加・バグ修正・リファクタを同じコミットに混ぜない。小さくまとめることで、レビューしやすくなり、問題が起きたときに切り戻しやすくなる。

コミットメッセージは**「何をしたか」を端的に書く場所。** diff を見ればわかることは書かず、変更の目的・背景を一行で残す。

### 4. PR の目安

**「コードを書いていない人が 30〜60 分でレビューできる単位」** を 1 PR の目安にする。

- 1 つの責務に集中している（機能追加 / リファクタ / バグ修正を混在させない）
- レビュアーが diff を見て「何のための PR か」を一読で理解できる
- 「実装＋レビュー合わせて半日以内」を超えそうなら分割を検討する

どう分割するかは担当者に委ねる。親 Issue の子Issue欄はあくまで参考。

PR作成時は `.github/pull_request_template.md` のテンプレートが自動で読み込まれる。

### 5. レビュー〜マージ

- レビュアーは最低 1 名のApproveを必須とする
- 指摘への対応が完了したら、作成者自身がマージする
- マージ後はブランチが自動削除される

---

## Claude Code を使った開発

このプロジェクトは Claude Code での開発を推奨しており、AI エージェント向けの設定が含まれている。

### AI エージェント設定

- **[AGENTS.md](AGENTS.md)**: Claude Code が読み込む開発ルール（技術スタック・コーディング規約・アーキテクチャルール）
- **[CLAUDE.md](CLAUDE.md)**: `@AGENTS.md` を参照するエントリーポイント

### インストール済みスキル

プロジェクトレベルで以下のスキルが設定されている（`.claude/skills/`）。

| スキル | 呼び出し方 | 用途 |
|---|---|---|
| software-architecture | 自動適用 | Clean Architecture・レイヤー分離の原則を実装時に参照 |
| webapp-testing | `/webapp-testing` | Playwright を使ったブラウザ自動テスト |
| feature-dev | `/feature-dev` | 仕様書を読み込んで機能を体系的に実装 |
| review-pr | `/review-pr` | PR を複数エージェントで並列レビュー |

### スキルの使い方

```
# 機能実装（仕様書を参照しながら進める）
/feature-dev ダッシュボード画面

# PR レビュー（マージ前に実行）
/review-pr

# ブラウザテスト
/webapp-testing GitHub OAuth のログインフローを検証して

# 設計原則の参照（実装中に常に意識する）
/software-architecture あなたが今書いているコードが Clean Architecture の原則に従っているか確認して
```

### 推奨: Claude Code の設定

Claude Code を初めて使う場合は以下を確認する。

1. [Claude Code のインストール](https://code.claude.com) — `npm install -g @anthropic-ai/claude-code`
2. プロジェクトルートで `claude` を起動すると CLAUDE.md / AGENTS.md が自動で読み込まれる
3. スキルは `/` で呼び出し可能（例: `/feature-dev`、`/review-pr`）
