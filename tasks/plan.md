# Implementation Plan: U-22 提出までの残タスク

## Overview

2026-08-24 の提出締め切りまでに、MVP の主要導線を `main` に統合し、本番環境で審査員が操作できる状態にする。ローカルの設計書、ブランチ、実装、テスト設定を 2026-08-20 時点で照合した。タスクは GitHub Projects で管理する方針のため、この文書は依存関係と実施順の索引とし、`tasks/todo.md` は作らない。

GitHub CLI の認証が切れており、Issue / Project の現在ステータスは取得できなかった。Issue 番号は `docs/roadmap.md` とコミット履歴に基づくため、再認証後に Projects 上の状態を照合する。

## Current State

- `feat/14-member-detail` には画面5と修正一式が実装済みだが、現在の `feat/18-distribution` には未統合。
- `feat/18-distribution` には画面7と分配API、スコア開示ゲートが実装済み。
- `origin/main` には本番 Compose 修正と `scripts/deploy.sh` が入っている。
- サイドバーの「サマリー生成」は未実装の `/projects/{id}/summaries` を指しており、404になる。
- フロントエンドの自動テストと `.github/workflows/` は存在しない。
- README のセットアップ・起動手順は「準備中」のまま。
- LLM の入力サイズ上限はあるが、利用回数・総コストの運用上限は未実装。

## Architecture Decisions

- 提出までのクリティカルパスは「AIなしの変化ログ + 分配 + 本番公開」とし、AIサマリーUIは後回しにできる。
- 未実装画面への導線は出さない。404を残したまま将来機能を予告しない。
- 完成済みの機能ブランチは再実装せず、`main` を基点に順番に統合して競合を解消する。
- 本番化前の検証は、ログイン → プロジェクト → ダッシュボード → メンバー詳細 → 分配の1本を最優先にする。

## Task List

### Phase 0: Release Integration — P0

- [ ] **#14 メンバー詳細を `main` へ統合**
  - Acceptance: `/projects/{id}/members/{login}` が表示でき、ダッシュボードから遷移できる。
  - Verification: frontend typecheck/build、該当画面の手動確認。
  - Dependencies: dashboard / changelog（実装済み）。
  - Scope: branch integration; conflicts in dashboard, changelog, docs require review.
- [ ] **#18 分配シミュレーションを最新 `main` へ統合**
  - Acceptance: 案の作成・編集理由付き保存・比較・確定・論理削除が一連で動く。
  - Verification: backend pytest、frontend typecheck/build、主要操作の手動確認。
  - Dependencies: #14 の統合順を先に確定し、双方が触る changelog / docs の競合を一度だけ解く。
  - Scope: branch integration.
- [x] **未実装サマリー画面への常設導線を外す**
  - Acceptance: サイドバーから存在しない `/summaries` に遷移できない。
  - Verification: frontend typecheck/build。
  - Dependencies: None.
  - Scope: XS, 1–2 files.

### Checkpoint: Integrated MVP

- [ ] backend tests pass.
- [ ] frontend typecheck and production build pass.
- [ ] ログイン → プロジェクト → ダッシュボード → メンバー詳細 → 分配が通る。

### Phase 1: Minimum Hardening — P0/P1

- [ ] **#66 / #36 最小のCI・フロントテスト基盤を追加**
  - Acceptance: PRで backend pytest、frontend typecheck/build、分配の純粋関数テストが自動実行される。
  - Verification: GitHub Actions の全ジョブ成功。
  - Dependencies: 統合後の `main`。
  - Scope: M, 3–5 files.
- [ ] **主要導線のブラウザ・スモークテスト**
  - Acceptance: 認証済みテストデータで主要5画面を開き、コンソールエラーと404がない。
  - Verification: 実ブラウザで記録を保存し、失敗箇所をIssue化。
  - Dependencies: 統合済みMVP、本番相当env。
  - Scope: M.
- [ ] **#39 LLM利用上限ガード**
  - Acceptance: 上限到達後は新規生成を拒否し、既存サマリーとAIなし機能は閲覧できる。
  - Verification: 上限直前・到達時・到達後のbackend tests。
  - Dependencies: #16 を提出版に含める場合のみP0。含めない場合はPost-submissionへ送る。
  - Scope: M.

### Checkpoint: Release Candidate

- [ ] 主要導線に致命的なエラーがない。
- [ ] AI停止時にもダッシュボードと分配が動く。
- [ ] マイグレーションが空DBと既存DBの両方で `head` まで通る。

### Phase 2: Production and Submission — P0

- [ ] **#37 本番デプロイ検証**
  - Acceptance: Cloudflare Tunnel + nginx + Next.js + FastAPI + PostgreSQL が再起動後も稼働する。
  - Verification: `/`, `/api/health`, OAuth callback、DB migration、主要導線を外部URLから確認。
  - Dependencies: Release Candidate、production secrets。
  - Scope: M.
- [ ] **ロールバック・バックアップ確認**
  - Acceptance: 直前イメージへの復帰手順とDBスナップショットの取得時刻が記録される。
  - Verification: stagingまたは複製環境で復帰確認。
  - Dependencies: deployment.
  - Scope: S.
- [ ] **デモ動画・Protopedia・U-22提出**
  - Acceptance: 外部公開URL、デモ動画、説明文、提出フォームが期限前に完了する。
  - Verification: 未ログインの別端末から公開URLと動画を確認。
  - Dependencies: production deployment.
  - Scope: M; GitHub Issue化が必要。

### Phase 3: Cuttable / Post-submission — P1/P2

- [ ] **#16 サマリー生成UI**
  - Acceptance: メンバー/PR単位の生成、進捗、失敗、再生成、既存結果を表示できる。
  - Verification: provider未設定・生成成功・部分失敗・再試行を確認。
  - Dependencies: #39 を同時に有効化。
  - Scope: M; 画面をメンバー/PR単位に縦断分割する。
- [ ] **#38 運用ドキュメントとREADME更新**
  - Acceptance: 初回セットアップ、起動、デプロイ、LLM設定、障害時の確認手順が再現可能。
  - Verification: 新しい環境で文書だけを使って起動できる。
  - Dependencies: production手順の確定。
  - Scope: M.
- [ ] **テスト網羅の拡充**
  - Acceptance: 認証境界、GitHub障害、分配の金額丸め、サマリージョブ競合の回帰テストがある。
  - Verification: CIで安定して成功する。
  - Dependencies: minimum CI.
  - Scope: 複数のS/Mタスクへ分割する。

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| #14 と #18 が別ブランチで長く分岐 | High | `main` を基点に1本ずつ統合し、各統合直後に全品質ゲートを通す |
| GitHub Projects の状態を取得できない | Medium | `gh auth login` 後に本計画とIssueのDone/In Progressを照合する |
| シェルのPATH次第でPython 3.6 / Node 19が選ばれ品質ゲートが失敗する | Medium | Python 3.11 / Node 20+を明示し、CIではバージョンを固定する |
| AI生成がコスト超過・障害を起こす | Medium | #16を提出版から外すか、#39とセットで有効化する |
| 提出直前の初回デプロイ | High | 8/20中に外部URLで検証し、残日を修正と予備日に使う |

## Open Questions

- GitHub Projects 上で #14 / #18 / #37 が現在どのレビュー・マージ状態か。
- 提出版で #16 を有効にするか。期限優先なら導線を閉じたまま提出する。
- 本番VM、ドメイン、OAuth App、Cloudflare Tunnel、LLM key の準備状況。
