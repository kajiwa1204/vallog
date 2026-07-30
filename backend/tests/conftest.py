"""テスト実行に必要な環境変数の既定値を、アプリのimportより前に用意する。

`app.core.config.Settings` は必須項目を持つため、環境変数がないと
テストモジュールのimport（collect）時点で ValidationError になる。conftest は
テストモジュールより先に読み込まれるので、ここで setdefault しておくことで
`pytest` を素で実行できるようにする。

setdefault なので、実環境の値を渡したいときは外から上書きできる。
"""

import base64
import os

# DBには接続しない（現状のテストはリポジトリをフェイクに差し替えている）。
# 実DBへの誤接続を静かに成功させないため、解決できないホストを指す
_DEFAULTS = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@db.invalid:5432/vallog_test",
    # Fernet が要求する形式（url-safe base64 の32バイト）を満たすダミー鍵
    "ENCRYPTION_KEY": base64.urlsafe_b64encode(b"vallog-test-encryption-key-32byt").decode(),
    "JWT_SECRET": "test-jwt-secret",
    "GITHUB_CLIENT_ID": "test-client-id",
    "GITHUB_CLIENT_SECRET": "test-client-secret",
    "FRONTEND_URL": "http://localhost:3000",
}

for key, value in _DEFAULTS.items():
    os.environ.setdefault(key, value)
