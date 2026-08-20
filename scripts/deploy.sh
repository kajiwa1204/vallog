#!/usr/bin/env bash
#
# 本番デプロイ。VM上のリポジトリルートで実行する（例: ssh vallog 'cd ~/vallog && ./scripts/deploy.sh'）。
#
# 本番構成では frontend/backend にボリュームマウントが無く、コードはイメージに
# 焼き込まれている。git pull だけでは反映されないため、リビルドまで含めて1コマンドにする。
#
# 使い方:
#   ./scripts/deploy.sh              # origin/main をデプロイ（確認あり）
#   ./scripts/deploy.sh feat/xxx     # 別のブランチをデプロイ
#   ASSUME_YES=1 ./scripts/deploy.sh # 確認を飛ばす（自動化用）
#   SKIP_MIGRATE=1 ./scripts/deploy.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

REF="${1:-main}"

# make を経由しない。Makefile 側の --profile production 対応（#121）の有無に関わらず
# 同じ挙動にするため。プロファイルを外すと cloudflared が起動せず公開されない
DC=(docker compose --env-file .env --profile production)

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m警告:\033[0m %s\n' "$1" >&2; }
die()  { printf '\033[1;31mエラー:\033[0m %s\n' "$1" >&2; exit 1; }

# ---------- 事前チェック ----------
[ -f .env ] || die ".env が見つかりません。scripts/setup_env.py prod で作成してください。"
command -v docker >/dev/null || die "docker が見つかりません。"

# 追跡ファイルに手を入れたままだと ff-only が失敗し、原因が分かりにくい。先に止める
if ! git diff --quiet || ! git diff --cached --quiet; then
  git status --short
  die "追跡ファイルに未コミットの変更があります。退避してから再実行してください。"
fi

# ---------- 取得する内容の提示 ----------
log "origin/$REF を取得中"
git fetch --quiet origin "$REF"

BEFORE="$(git rev-parse HEAD)"
AFTER="$(git rev-parse "origin/$REF")"

if [ "$BEFORE" = "$AFTER" ]; then
  echo "すでに最新です（$(git rev-parse --short HEAD)）。イメージの再作成のみ行います。"
else
  echo "これから取り込むコミット:"
  git --no-pager log --oneline "$BEFORE".."$AFTER"
fi

if [ "${ASSUME_YES:-0}" != "1" ]; then
  printf '\n続行しますか? [y/N] '
  read -r answer
  case "$answer" in
    [yY]) ;;
    *) echo "中止しました。"; exit 0 ;;
  esac
fi

# ---------- 反映 ----------
if [ "$BEFORE" != "$AFTER" ]; then
  log "$REF に更新"
  git checkout --quiet "$REF"
  git merge --ff-only --quiet "origin/$REF"
fi

log "イメージをビルドしてコンテナを差し替え"
# --build はキャッシュを使う。変更のあったサービスだけが再作成され、db と nginx は触られない。
# 依存関係を作り直したい場合のみ make build ENV=prod（--no-cache）を使う
"${DC[@]}" up -d --build

log "nginx の接続先を更新"
# nginx は起動時に解決した Compose サービスの IP を保持するため、
# frontend/backend の差し替え後に graceful reload して新しい IP を解決させる。
"${DC[@]}" exec -T nginx nginx -t
"${DC[@]}" exec -T nginx nginx -s reload

if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
  log "マイグレーション適用"
  # heads（複数形）を使う。単一headでも動き、head が分岐していても止まらない。
  # 分岐そのものは修正対象（#116）であって、デプロイを止める理由にはしない
  "${DC[@]}" exec -T backend alembic upgrade heads
fi

# ---------- 疎通確認 ----------
log "疎通確認"
failed=0
for i in $(seq 30); do
  if curl -fsS -o /dev/null --max-time 5 http://localhost/ 2>/dev/null; then break; fi
  [ "$i" = 30 ] && failed=1
  sleep 2
done
[ "$failed" = 0 ] && echo "  フロントエンド (/)      OK" || echo "  フロントエンド (/)      NG"

if curl -fsS -o /dev/null --max-time 5 http://localhost/api/docs 2>/dev/null; then
  echo "  バックエンド (/api)     OK"
else
  echo "  バックエンド (/api)     NG"
  failed=1
fi

"${DC[@]}" ps --format "table {{.Name}}\t{{.Status}}"

if [ "$failed" != 0 ]; then
  warn "疎通確認に失敗しました。ログ: ${DC[*]} logs --tail 50"
  warn "切り戻す場合: ./scripts/deploy.sh でこのコミットを指定 → $BEFORE"
  exit 1
fi

log "完了（$(git rev-parse --short HEAD)）"
