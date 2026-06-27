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
│   │   └── api.ts                                # APIクライアント（fetch wrapper）
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
