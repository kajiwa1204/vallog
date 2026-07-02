# Vallog — ディレクトリ構成

> **注意**: 各ディレクトリ内のファイルは配置例です。ファイル名・ファイル数は実装に応じて変わります。遵守すべきはディレクトリ構成のみです。

## backend/

```
backend/
├── app/
│   ├── main.py                      # FastAPIアプリのエントリーポイント
│   ├── core/
│   │   ├── config.py                # 環境変数・設定（Pydantic Settings）
│   │   ├── database.py              # async engine・session
│   │   ├── errors.py               # AppError・ErrorCode・例外ハンドラ
│   │   └── security.py             # JWTトークン検証
│   ├── routers/                     # モデルごとにエンドポイントを配置
│   │   ├── auth.py                  # POST /auth/github, POST /auth/refresh
│   │   ├── projects.py              # GET/POST /projects, GET/PATCH /projects/{id}
│   │   ├── members.py               # GET /projects/{id}/members
│   │   ├── scores.py                # GET /projects/{id}/scores
│   │   ├── distribution.py          # GET/POST /projects/{id}/distributions
│   │   └── summaries.py             # POST /projects/{id}/summaries
│   ├── models/                      # SQLAlchemyモデル（エンティティ対応）
│   │   ├── user.py                  # User
│   │   ├── project.py               # Project, ProjectMember, InvitationLink
│   │   ├── github_cache.py          # GitHubPullRequest, GitHubIssue, GitHubReview, GitHubIssueAssignee
│   │   ├── distribution.py          # DistributionProposal, DistributionItem, DistributionEditLog
│   │   └── summary.py               # ContributionSummary
│   ├── schemas/                     # Pydanticスキーマ（request/response）
│   │   ├── user.py                  # UserResponse
│   │   ├── project.py               # ProjectCreate, ProjectResponse
│   │   ├── score.py                 # ScoreResponse, MemberScore
│   │   ├── distribution.py          # ProposalCreate, ProposalResponse, ItemUpdate
│   │   └── summary.py               # SummaryResponse
│   ├── services/                    # ビジネスロジック
│   │   ├── github.py                # GitHub APIクライアント・TTLキャッシュ管理
│   │   ├── scoring.py               # スコア計算ロジック
│   │   └── claude.py                # 貢献サマリー生成（Claude API）
│   └── repositories/                # DBアクセス層
│       ├── project.py               # ProjectRepository
│       ├── github_cache.py          # GitHubCacheRepository
│       ├── distribution.py          # DistributionRepository
│       └── summary.py               # SummaryRepository
├── alembic/
│   ├── env.py
│   └── versions/
├── requirements.txt
└── Dockerfile
```

## frontend/

```
frontend/
├── src/
│   ├── app/                                      # Next.js App Router
│   │   ├── layout.tsx                            # ルートレイアウト
│   │   ├── page.tsx                              # ログイン（画面1）
│   │   ├── projects/
│   │   │   ├── page.tsx                          # プロジェクト一覧（画面2）
│   │   │   └── [id]/
│   │   │       ├── settings/page.tsx             # プロジェクト設定（画面3）
│   │   │       ├── dashboard/page.tsx            # ダッシュボード（画面4）
│   │   │       ├── members/[login]/page.tsx      # メンバー詳細（画面5）
│   │   │       └── distribution/page.tsx         # 分配シミュレーション（画面7）
│   │   └── invite/[token]/page.tsx               # 招待リンク経由
│   ├── components/
│   │   └── ui/                                   # 汎用コンポーネント（自前実装）
│   │       ├── Button.tsx
│   │       ├── Button.module.css
│   │       ├── Modal.tsx
│   │       ├── Modal.module.css
│   │       ├── Input.tsx
│   │       └── Input.module.css
│   ├── features/                                 # 機能別コンポーネント（画面内フラット）
│   │   ├── dashboard/
│   │   │   ├── MemberCard.tsx
│   │   │   ├── MemberCard.module.css
│   │   │   ├── ScoreChart.tsx
│   │   │   ├── ScoreChart.module.css
│   │   │   └── useDashboard.ts
│   │   ├── distribution/
│   │   │   ├── AllocationTable.tsx
│   │   │   ├── AllocationTable.module.css
│   │   │   ├── SummaryPanel.tsx
│   │   │   ├── SummaryPanel.module.css
│   │   │   ├── EditHistoryTimeline.tsx
│   │   │   ├── EditHistoryTimeline.module.css
│   │   │   └── useDistribution.ts
│   │   ├── members/
│   │   │   ├── ScoreBreakdown.tsx
│   │   │   ├── ScoreBreakdown.module.css
│   │   │   ├── ContributionSummary.tsx
│   │   │   ├── ContributionSummary.module.css
│   │   │   └── useMemberDetail.ts
│   │   └── projects/
│   │       ├── ProjectCard.tsx
│   │       ├── ProjectCard.module.css
│   │       ├── WeightEditor.tsx
│   │       ├── WeightEditor.module.css
│   │       └── useProjects.ts
│   ├── hooks/
│   │   └── useAuth.ts                            # 認証状態管理（features横断）
│   ├── lib/
│   │   ├── api.ts                                # トランスポート専任（fetch・認証・ApiError正規化）
│   │   └── errorMessages.ts                      # APIエラーのユーザー向け日本語化（i18n）
│   ├── types/
│   │   └── index.ts                              # features横断の共通型定義
│   └── constants/
│       └── index.ts                              # API_BASE_URLなど定数
├── next.config.ts
├── tsconfig.json
└── package.json
```

## 設計上の判断

| 項目 | 判断 |
|---|---|
| バックエンドAPIのバージョニング | `api/v1/` は不採用。MVPではフロントが唯一のクライアントのため過剰設計 |
| フロントのコンポーネント設計 | Atomic Design は不採用。featuresベースのフラット構成 |
| features内の分割 | 基本はフラット。ファイルが増えてきたら hooks/ などのサブディレクトリに分けてよい |
| routers からのDBアクセス | 原則 `routers → services → repositories`。例外として、**単一 repository メソッドを1回呼んで結果をそのまま返す参照（GET）のみ** `routers` から `repository` を直接呼んでよい。リクエスト由来の絞り込み（例: `GET /projects` で自分がメンバーのプロジェクトのみ取得）は許容する。所有チェックによる拒否・複数 repository・集約・キャッシュ・書き込みが入ったら `services` を経由する。判定基準は AGENTS.md「バックエンド」を正とする。 |
| repositories の書き込みメソッドの入力型 | 単純追加はORMモデルインスタンス、真のupsertはDTO（詳細は本ファイル末尾の「repositoriesの書き込みメソッド: ORMインスタンス vs DTO」を参照） |

### repositoriesの書き込みメソッド: ORMインスタンス vs DTO

`repositories/` の書き込み系メソッドは、何を受け取るかが2パターンに分かれる。

- `repositories/project.py`（`ProjectRepository.create` など）: ORMモデルインスタンス（`Project` など）をそのまま受け取り、`db.add(instance)` する
- `repositories/github_cache.py`（`GitHubCacheRepository.upsert_pull_requests` など）: `dataclass` のDTO（`PullRequestData` など）を受け取り、`sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)` に渡す

この判断は2段階に分かれる。1段目はSQLAlchemyのAPI仕様による強制、2段目はそこから先の任意の設計選択。

**1段目: ORMインスタンスを使うか、プレーンなデータにするか（これはAPI仕様で強制される）**

- ORMの `Session` API（`db.add()` / `db.merge()`）は、セッションに紐づく「生きたオブジェクト」を前提にしている。`relationship` によるcascade、Python側のdefault（`default=uuid.uuid4` 等）、identity mapはこの仕組みの上に成り立っており、ORMモデルインスタンスをそのまま渡すのが最も素直で無駄がない
- Coreの `insert()` API（`ON CONFLICT DO UPDATE` を使う真のupsertはこちらでしか書けない）は、セッションに紐づかないプレーンな「列名→値」の辞書を要求する。ORMモデルインスタンスを直接渡す口はないため、upsertする時点で何らかの形でプレーンなデータへの変換が必要になる

**2段目: プレーンなデータを型付きDTOにするか、辞書のまま・フィールドべた書きにするか（ここはAPI仕様に強制されない任意の選択）**

Coreの `insert()` が要求するのは「列名→値の辞書」でしかなく、`list[dict]` をそのまま `_build_pull_request_rows` から `upsert_pull_requests` に渡す実装でも動く。DTO（`@dataclass`）にしているのはそちらを選ばなかった、という設計判断で、理由は以下:

- サービス層でDTOを組み立てる際、フィールド名の誤り（例: `gh_created_at` を `created_at` と書き間違える）が構築時点で型チェッカーに検出される。辞書だと `KeyError` が実行時、しかも呼び出し元から離れたSQL構築のタイミングで初めて発生する
- `PullRequestData(github_id=..., number=..., ...)` という呼び出しがそのままフィールド一覧のドキュメントになる。辞書リテラルや `**kwargs` はリポジトリの実装を読まないと何のフィールドが必要か分からない
- `backend/app/services/llm.py` の `LLMResult` など、このコードベースは元々サービス境界の構造化データに `@dataclass` を使う慣習がある。辞書のべた書きはその慣習からの逸脱になる

したがって判断基準は次の通り:

> **単純追加（`db.add()` で足りる）ならORMモデルインスタンスをそのまま受け取る。真のupsert（`ON CONFLICT DO UPDATE`）が必要ならDTOを受け取る。**

なぜ全部同じ形に統一しないか:

- 全部DTOにすると、単純追加側（`ProjectRepository` 等）で `db.add()` の直前に `Model(**dto.__dict__)` のような無駄な変換コードが必要になる。ORMインスタンスを直接組み立てれば不要な層
- 全部ORMインスタンス経由にすると、upsert側（`GitHubCacheRepository` 等）で「既存行をSELECTで探す→あれば属性を書き換える／なければ新規addする」というPython側の分岐ロジックを自前で書く必要が生まれる。`ON CONFLICT DO UPDATE` なら1回のSQLでこの分岐をPostgres側に任せられ、DBラウンドトリップも少なく、行の主キー（`id`）も同期のたびに変わらず安定する（`pr_summaries` のような将来のFK参照を壊さないために重要）

副次的な利点として、DTOを経由する設計はGitHubの生JSON→DTOへの変換関数（`_build_pull_request_rows` 等）をDBセッション不要の純粋関数にできるため、実DBなしでユニットテストしやすくなる（`backend/tests/test_github_cache.py` 参照）。
