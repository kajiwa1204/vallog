# Conventional Commits ガイド



## 基本フォーマット

```
<type>(<scope>): <subject>
```

例:
```
feat(auth): GitHub OAuth ログインを実装
fix(api): リフレッシュトークンの二重使用を防ぐ
```

### 各パーツの意味

| パーツ | 説明 | 省略 |
|---|---|---|
| `type` | 変更の種類（後述） | 不可 |
| `scope` | 変更対象のモジュール・機能 | 可 |
| `subject` | 変更内容の一言要約 | 不可 |

---

## type 一覧

よく使うものから順に

| type | 使う場面 | 例 |
|---|---|---|
| `feat` | 新機能を追加した | `feat(project): プロジェクト作成APIを追加` |
| `fix` | バグを修正した | `fix(auth): トークン期限切れ時の500エラーを修正` |
| `refactor` | 動作を変えずにコードを整理した | `refactor(user): リポジトリ層の重複処理を統合` |
| `docs` | ドキュメント・コメントのみ変更 | `docs: CLAUDE.mdにコマンド一覧を追加` |
| `test` | テストを追加・修正した | `test(auth): OAuthコールバックのユニットテストを追加` |
| `chore` | ビルド設定・依存関係など雑多な作業 | `chore: alembicの初期設定を追加` |
| `style` | コードの動作に影響しない整形 | `style: インデントをスペース4つに統一` |
| `perf` | パフォーマンス改善 | `perf(db): N+1クエリを解消` |
| `ci` | CI/CDの設定変更 | `ci: GitHub Actionsにlintジョブを追加` |
| `revert` | 以前のコミットを取り消した | `revert: feat(auth): GitHub OAuthを元に戻す` |

---

## subject の書き方

- **動詞から始める**（命令形）: 「〜を追加」「〜を修正」「〜を削除」
- **何をしたかを書く**（なぜはPRの説明欄へ）
- **50文字以内**を目安に
- 末尾に句点（。）はつけない

**OK例:**
```
feat(member): メンバー招待リンクの生成APIを実装
fix(project): プロジェクト削除時に関連データも削除するよう修正
```

**NG例:**
```
feat: 色々実装した          ← 何をしたかわからない
fix: バグを直した。         ← 何のバグ？ 句点もNG
feat(auth): github oauth    ← 日本語プロジェクトなら日本語で
```

---

## scope の決め方

このプロジェクトでは以下を目安にしてください

| scope | 対象 |
|---|---|
| `auth` | 認証・認可 |
| `project` | プロジェクトCRUD |
| `member` | メンバー管理・招待 |
| `user` | ユーザー情報 |
| `github` | GitHub API連携 |
| `db` | DB・マイグレーション |
| `infra` | Docker・nginx・Cloudflare |
| `api` | API全般（特定scopeに当てはまらない場合） |

scope が複数にまたがる場合は省略してOK

---

## 実例集

```bash
# 新機能
feat(project): プロジェクト一覧・詳細・作成・削除APIを実装
feat(member): 招待リンク生成とメンバー登録エンドポイントを追加

# バグ修正
fix(auth): refreshトークンのjti検証が失敗した場合に401を返すよう修正
fix(infra): nginxで/apiプレフィックスをstripしてバックエンドに転送

# リファクタリング
refactor(user): get_or_create_userをリポジトリ層に移動

# インフラ・設定
chore(db): projectsテーブルのマイグレーションを追加
ci: Dockerfileのキャッシュ最適化

# ドキュメント
docs: conventional commitsガイドを追加
```

---

## よくある疑問

**Q. feat と fix の判断が難しい**  
A. 「新しく動くようになった」→ `feat`、「壊れていたものが直った」→ `fix`。新機能のバグを同時に直した場合は、主な変更に合わせる。

**Q. 複数の変更をまとめてコミットしていい？**  
A. 理想は1コミット1変更ですが、密接に関連するものはまとめてOKです。まとめたときに subject が「〇〇と△△と□□を修正」のように長くなるなら、コミットを分けるサインです。

**Q. WIPコミットはどうする？**  
A. ローカルブランチでの作業中は自由にコミットして構いません。PRを出す前に `git rebase -i` でまとめて整理するのがベストプラクティスです。

---

## まとめ

1. `type(scope): subject` の形で書く
2. `type` は `feat` / `fix` / `refactor` / `chore` / `docs` が8割
3. subject は「何をしたか」を動詞から始めて50字以内で
4. 迷ったら「未来の自分がこのメッセージだけで変更内容を理解できるか？」を基準にする
