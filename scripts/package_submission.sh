#!/usr/bin/env bash
#
# U-22 提出用のソースコードzipを作る。
#
# 対象は git の追跡ファイルだけ。.env や .codex/config.toml のような未追跡
# ファイルは構造的に混入しない。「除外し忘れ」ではなく「入りようがない」状態
# にするのがこのスクリプトの目的で、EXCLUDE はその上で提出物として不要な
# ものを落とすためのもの。
#
# 使い方:
#   ./scripts/package_submission.sh                        # dist/vallog-submission.zip を作る
#   OUT=~/Desktop/vallog.zip ./scripts/package_submission.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="${OUT:-dist/vallog-submission.zip}"

# 提出物から落とすパス（git ls-files の出力に対する拡張正規表現）
EXCLUDE=(
  '^\.claude/'                        # AIエージェント設定。Apache-2.0 の第三者コードを含み、第三者OSS申告を増やしたくないため
  '^docs/roadmap\.md$'                # 内部の進捗管理（Milestone・Issue番号・遅延の記録）
  '^docs/conventional_commits\.md$'   # チーム内のコミット規約
  '^docs/business_model\.md$'         # 事業計画は仮決定。聞かれたときに出す資料で、提出物の一部にはしない
)

# zip に入っていたら中断する（漏洩に直結するもの）
FORBIDDEN='(^|/)\.env$|(^|/)\.env\.local$|^\.codex/|^\.agents/|(^|/)settings\.local\.json$'

# 中身を走査して検出したら中断するトークン形式
SECRET_PATTERNS='github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}'

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m警告:\033[0m %s\n' "$1" >&2; }
die()  { printf '\033[1;31mエラー:\033[0m %s\n' "$1" >&2; exit 1; }

command -v zip >/dev/null || die "zip が見つかりません。"
git rev-parse --git-dir >/dev/null 2>&1 || die "git リポジトリではありません。"

# ---------- 対象の決定 ----------
# zip にはワーキングツリーの現在の内容が入る。コミット済みの状態と食い違って
# いても止めはしないが、意図しない差分が固まらないよう知らせる
if ! git diff --quiet || ! git diff --cached --quiet; then
  warn "未コミットの変更があります。zip にはワーキングツリーの現在の内容が入ります。"
  git status --short
fi

pattern="$(IFS='|'; echo "${EXCLUDE[*]}")"
if [ -n "$pattern" ]; then
  files="$(git ls-files | grep -Ev "$pattern")"
else
  files="$(git ls-files)"
fi
[ -n "$files" ] || die "対象ファイルがありません。"

# ---------- 事前検査 ----------
log "対象の検査"
hits="$(printf '%s\n' "$files" | grep -E "$FORBIDDEN" || true)"
if [ -n "$hits" ]; then
  printf '%s\n' "$hits" >&2
  die "秘密情報を含みうるファイルが対象に入っています。.gitignore と追跡状態を確認してください。"
fi
echo "  禁止パス            なし"

# 除外したファイルへのリンクが残ると、提出物の中でリンク切れになる
excluded_files="$(git ls-files | grep -E "$pattern" || true)"
dangling=0
while IFS= read -r excluded; do
  [ -n "$excluded" ] || continue
  refs="$(printf '%s\n' "$files" | tr '\n' '\0' | xargs -0 grep -l -F -- "$excluded" 2>/dev/null || true)"
  if [ -n "$refs" ]; then
    warn "除外した $excluded が以下から参照されています（提出物ではリンク切れになります）"
    printf '%s\n' "$refs" | sed 's/^/    /' >&2
    dangling=1
  fi
done <<< "$excluded_files"
[ "$dangling" = 0 ] && echo "  リンク切れ          なし"

# ---------- 生成 ----------
log "zip を作成"
mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
# -X: macOS の拡張属性を含めない（提出物に __MACOSX を作らない）
printf '%s\n' "$files" | zip -q -X "$OUT" -@

# ---------- 事後検証 ----------
# 対象リストの検査だけでは、追跡ファイルの「中身」に書かれたトークンを拾えない
log "中身を検証"
found="$(unzip -p "$OUT" | grep -aoE "$SECRET_PATTERNS" | sort -u || true)"
if [ -n "$found" ]; then
  printf '%s\n' "$found" >&2
  rm -f "$OUT"
  die "zip の中に認証トークン形式の文字列が見つかりました。zip は削除しました。"
fi
echo "  トークン形式        検出なし"

count="$(printf '%s\n' "$files" | wc -l | tr -d ' ')"
size="$(du -h "$OUT" | cut -f1 | tr -d ' ')"

log "完了: ${OUT}（${count} ファイル / ${size}）"
printf '%s\n' "$files" | awk -F/ '{print ($2 == "" ? "(ルート)" : $1)}' | sort | uniq -c | sort -rn | sed 's/^/  /'
