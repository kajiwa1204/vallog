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
| ORM / マイグレーション | SQLAlchemy (asyncio) + Alembic |
| DB | PostgreSQL |
| 認証 | GitHub OAuth |
| インフラ | Docker Compose + Cloudflare Tunnel + nginx |

---

## ローカル開発環境

> **注意**: インフラ構成確定後に追記する。

### 前提条件

- Docker / Docker Compose
- Node.js 20+
- Python 3.11+

### セットアップ

```bash
# 準備中
```

### 開発サーバー起動

```bash
# 準備中
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
