"""認証セッション（リフレッシュトークンのローテーション）と OAuth state 検証のテスト。

DBは使わず、RefreshTokenRepository をインメモリのフェイクに差し替えて
services/auth.py の判定ロジックだけを検証する。
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.core.security import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.models.refresh_token import RefreshToken
from app.services.auth import rotate_session

_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class FakeRefreshTokenRepo:
    """RefreshTokenRepository のインメモリ版。コミットは呼び出し側の責務なので持たない。"""

    def __init__(self, tokens: list[RefreshToken] | None = None):
        self.rows: dict[uuid.UUID, RefreshToken] = {t.jti: t for t in tokens or []}

    async def create(self, *, jti, user_id, expires_at):
        row = RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at)
        self.rows[jti] = row
        return row

    async def get_by_jti(self, jti, *, for_update=False):
        return self.rows.get(jti)

    async def revoke(self, jti):
        if jti in self.rows:
            self.rows[jti].revoked_at = datetime.now(timezone.utc)

    async def revoke_all_for_user(self, user_id):
        now = datetime.now(timezone.utc)
        for row in self.rows.values():
            if row.user_id == user_id and row.revoked_at is None:
                row.revoked_at = now

    async def rotate(self, *, old_jti, user_id, expires_at):
        new_jti = uuid.uuid4()
        if old_jti in self.rows:
            self.rows[old_jti].revoked_at = datetime.now(timezone.utc)
        self.rows[new_jti] = RefreshToken(
            jti=new_jti, user_id=user_id, expires_at=expires_at
        )
        return new_jti

    async def delete_expired_for_user(self, user_id, now):
        for jti in [
            jti
            for jti, row in self.rows.items()
            if row.user_id == user_id and row.expires_at < now
        ]:
            del self.rows[jti]


def _live_token(**overrides) -> RefreshToken:
    defaults = dict(
        jti=uuid.uuid4(),
        user_id=_USER_ID,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        revoked_at=None,
    )
    defaults.update(overrides)
    return RefreshToken(**defaults)


async def _rotate(repo: FakeRefreshTokenRepo, token: str | None):
    user = MagicMock(id=_USER_ID)
    user_repo = MagicMock(get_by_id=AsyncMock(return_value=user))
    with (
        patch("app.services.auth.RefreshTokenRepository", return_value=repo),
        patch("app.services.auth.UserRepository", return_value=user_repo),
    ):
        return await rotate_session(AsyncMock(), token)


async def test_rotate_revokes_old_token_and_issues_a_live_successor():
    row = _live_token()
    repo = FakeRefreshTokenRepo([row])

    session = await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    _, new_jti = decode_refresh_token(session.refresh_token)
    assert row.revoked_at is not None
    assert repo.rows[new_jti].revoked_at is None


async def test_rotate_takes_a_row_lock():
    """行ロックを取らないと並行リクエストがチェーンを分岐させる。"""
    row = _live_token()
    repo = FakeRefreshTokenRepo([row])
    calls: list[bool] = []
    original = repo.get_by_jti

    async def spy(jti, *, for_update=False):
        calls.append(for_update)
        return await original(jti, for_update=for_update)

    repo.get_by_jti = spy  # type: ignore[method-assign]
    await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    assert calls == [True]


async def test_revoked_token_is_always_reuse_and_revokes_every_token():
    """失効済みトークンの再送は、失効直後であっても無条件で全失効させる。

    誤爆の回避はクライアント側（navigator.locks によるタブ間直列化）の責務で、
    サーバ側は猶予期間を持たない。猶予はサーバが検証できない当て推量であり、
    その間隔でポーリングすれば再利用検知を恒久的に無効化できてしまう。
    """
    other_live = _live_token()
    row = _live_token(revoked_at=datetime.now(timezone.utc))
    repo = FakeRefreshTokenRepo([row, other_live])

    with pytest.raises(AppError) as exc:
        await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    assert exc.value.code == ErrorCode.AUTH_TOKEN_REUSE_DETECTED
    # 同一ユーザーの生きているトークンも巻き込んで失効させる
    assert other_live.revoked_at is not None


async def test_reuse_immediately_after_rotation_is_still_reuse():
    """猶予期間を持たないことを、実際にローテーションした直後の再送で固定する。"""
    row = _live_token()
    repo = FakeRefreshTokenRepo([row])
    old_token = create_refresh_token(_USER_ID, row.jti)

    first = await _rotate(repo, old_token)
    _, successor_jti = decode_refresh_token(first.refresh_token)

    with pytest.raises(AppError) as exc:
        await _rotate(repo, old_token)

    assert exc.value.code == ErrorCode.AUTH_TOKEN_REUSE_DETECTED
    assert repo.rows[successor_jti].revoked_at is not None


async def test_token_belonging_to_another_user_is_rejected():
    """JWTの sub とDB行の持ち主が食い違ったまま進むと他人のトークンを発行しうる。"""
    row = _live_token(user_id=uuid.uuid4())
    repo = FakeRefreshTokenRepo([row])

    with pytest.raises(AppError) as exc:
        await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    assert exc.value.code == ErrorCode.AUTH_INVALID_TOKEN


async def test_token_expired_in_db_is_rejected():
    """JWTの exp がまだ生きていても、DB側の期限切れで拒否する。"""
    row = _live_token(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    repo = FakeRefreshTokenRepo([row])

    with pytest.raises(AppError) as exc:
        await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    assert exc.value.code == ErrorCode.AUTH_INVALID_TOKEN


async def test_unknown_jti_is_rejected():
    repo = FakeRefreshTokenRepo()

    with pytest.raises(AppError) as exc:
        await _rotate(repo, create_refresh_token(_USER_ID, uuid.uuid4()))

    assert exc.value.code == ErrorCode.AUTH_INVALID_TOKEN


async def test_missing_cookie_is_rejected():
    with pytest.raises(AppError) as exc:
        await _rotate(FakeRefreshTokenRepo(), None)

    assert exc.value.code == ErrorCode.AUTH_REFRESH_TOKEN_MISSING


async def test_access_token_is_not_accepted_as_refresh_token():
    with pytest.raises(AppError) as exc:
        await _rotate(FakeRefreshTokenRepo(), create_access_token(_USER_ID))

    assert exc.value.code == ErrorCode.AUTH_INVALID_TOKEN


async def test_rotate_prunes_expired_rows():
    row = _live_token()
    stale = _live_token(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    repo = FakeRefreshTokenRepo([row, stale])

    await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    assert stale.jti not in repo.rows
    # 失効済みでも期限内の行は再利用検知に必要なので残す
    assert row.jti in repo.rows


# --- 本物の RefreshTokenRepository が発行するSQL ---
#
# 上のテストはリポジトリをフェイクに差し替えているため、実際に発行されるSQLは
# 検証できていない（フェイクが本番ロジックを再実装しており、本物が壊れても緑の
# まま通る）。実DBに繋ぐ結合テストの基盤整備は #70 のスコープなので、ここでは
# 本物のリポジトリを呼び、セッションが受け取った文をコンパイルして突き合わせる。


class _RecordingSession:
    """execute() に渡された文を記録するだけの AsyncSession スタブ。"""

    def __init__(self):
        self.statements = []
        self.added = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return MagicMock()

    def add(self, obj):
        self.added.append(obj)

    def compiled(self, index: int = 0) -> str:
        from sqlalchemy.dialects import postgresql

        return str(self.statements[index].compile(dialect=postgresql.dialect()))


def _repo() -> tuple[object, _RecordingSession]:
    from app.repositories.refresh_token import RefreshTokenRepository

    session = _RecordingSession()
    return RefreshTokenRepository(session), session


async def test_get_by_jti_takes_a_row_lock_only_when_asked():
    repo, session = _repo()

    await repo.get_by_jti(uuid.uuid4())
    assert "FOR UPDATE" not in session.compiled(0)

    await repo.get_by_jti(uuid.uuid4(), for_update=True)
    assert "FOR UPDATE" in session.compiled(1)


async def test_rotate_revokes_the_old_row_and_inserts_a_new_one():
    repo, session = _repo()

    new_jti = await repo.rotate(
        old_jti=uuid.uuid4(), user_id=_USER_ID, expires_at=datetime.now(timezone.utc)
    )

    sql = session.compiled(0)
    assert "UPDATE refresh_tokens SET revoked_at" in sql
    # 後継への参照はもう持たない（猶予期間の撤回に伴い削除）
    assert "replaced_by" not in sql
    assert [row.jti for row in session.added] == [new_jti]


async def test_delete_expired_keeps_revoked_but_unexpired_rows():
    """WHERE が user_id と expires_at だけで絞られている（revoked_at を見ない）。"""
    repo, session = _repo()

    await repo.delete_expired_for_user(_USER_ID, datetime.now(timezone.utc))

    sql = session.compiled(0)
    assert sql.startswith("DELETE FROM refresh_tokens")
    assert "user_id =" in sql
    assert "expires_at <" in sql
    assert "revoked_at" not in sql


async def test_revoke_all_for_user_only_touches_live_rows():
    repo, session = _repo()

    await repo.revoke_all_for_user(_USER_ID)

    sql = session.compiled(0)
    assert "UPDATE refresh_tokens SET revoked_at" in sql
    assert "user_id =" in sql
    assert "revoked_at IS NULL" in sql


def test_refresh_token_model_has_no_rotation_chain_column():
    assert "replaced_by_jti" not in RefreshToken.__table__.columns
    # user_id の索引は全失効・掃除の WHERE で使うため残す
    assert any(
        list(index.columns) == [RefreshToken.__table__.c.user_id]
        for index in RefreshToken.__table__.indexes
    )


# --- OAuth state 検証（ログインCSRF対策） ---


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    app.dependency_overrides[get_db] = lambda: MagicMock()
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_login_sets_state_cookie_scoped_to_auth_path(client):
    res = client.get("/auth/github")

    assert res.status_code == 307
    cookie = next(
        c
        for c in res.headers.get_list("set-cookie")
        if c.startswith("github_oauth_state=") and 'github_oauth_state=""' not in c
    )
    assert "HttpOnly" in cookie
    assert "Path=/api/auth" in cookie


def test_callback_rejects_mismatched_state(client):
    client.cookies.set("github_oauth_state", "expected-state")

    with patch("app.routers.auth.login_with_github_code", new=AsyncMock()) as login:
        res = client.get("/auth/github/callback?code=abc&state=attacker-state")

    assert "error=auth_state_mismatch" in res.headers["location"]
    login.assert_not_awaited()


def test_callback_rejects_non_ascii_state_without_erroring(client):
    """compare_digest は str 同士だと非ASCIIで TypeError になる（＝未認証で踏める500）。"""
    client.cookies.set("github_oauth_state", "expected-state")

    with patch("app.routers.auth.login_with_github_code", new=AsyncMock()) as login:
        res = client.get("/auth/github/callback?code=abc&state=あいう")

    assert res.status_code == 307
    assert "error=auth_state_mismatch" in res.headers["location"]
    login.assert_not_awaited()


def test_callback_rejects_absurdly_long_state_without_erroring(client):
    # 非ASCII1文字は %XX%XX%XX の9文字になるため、httpx のURL成分上限(65536)に
    # 収まる範囲で最大級にする（5000文字 → エンコード後45KB）
    client.cookies.set("github_oauth_state", "expected-state")

    with patch("app.routers.auth.login_with_github_code", new=AsyncMock()) as login:
        res = client.get(f"/auth/github/callback?code=abc&state={'あ' * 5_000}")

    assert res.status_code == 307
    assert "error=auth_state_mismatch" in res.headers["location"]
    login.assert_not_awaited()


def test_callback_rejects_missing_state_cookie(client):
    with patch("app.routers.auth.login_with_github_code", new=AsyncMock()) as login:
        res = client.get("/auth/github/callback?code=abc&state=some-state")

    assert "error=auth_state_mismatch" in res.headers["location"]
    login.assert_not_awaited()


def test_logout_also_clears_the_legacy_root_scoped_cookie(client):
    """path を絞る前に発行された Path=/ の Cookie が残ると refresh が壊れ続ける。"""
    res = client.post("/auth/logout")

    paths = {
        c.split("Path=")[1].split(";")[0]
        for c in res.headers.get_list("set-cookie")
        if "refresh_token=" in c
    }
    assert paths == {"/api/auth", "/"}


# --- /auth/refresh が401のときのCookie掃除 ---


def _refresh_cookie_paths(res) -> set[str]:
    return {
        c.split("Path=")[1].split(";")[0]
        for c in res.headers.get_list("set-cookie")
        if 'refresh_token=""' in c
    }


def test_refresh_clears_cookies_when_rotation_fails(client):
    """死んだCookieを持ち続けると useAuth が毎マウントで401を繰り返し復帰できない。

    FastAPI は例外送出時に response パラメータの Set-Cookie をマージしないため、
    AppError に積んで app_error_handler 側で出す必要がある。
    """
    with patch(
        "app.routers.auth.rotate_session",
        new=AsyncMock(
            side_effect=AppError(
                401, ErrorCode.AUTH_TOKEN_REUSE_DETECTED, "Token reuse detected"
            )
        ),
    ):
        res = client.post("/auth/refresh")

    assert res.status_code == 401
    assert res.json()["code"] == "AUTH_TOKEN_REUSE_DETECTED"
    # 新Path・旧Path（移行前の Path=/）の両方を消す
    assert _refresh_cookie_paths(res) == {"/api/auth", "/"}


def test_refresh_error_response_has_no_duplicate_headers(client):
    """Set-Cookie だけを足すこと。捨てResponseの content-length を混ぜてはいけない。"""
    with patch(
        "app.routers.auth.rotate_session",
        new=AsyncMock(
            side_effect=AppError(401, ErrorCode.AUTH_INVALID_TOKEN, "Invalid token")
        ),
    ):
        res = client.post("/auth/refresh")

    assert len(res.headers.get_list("content-length")) == 1
    assert res.json()["detail"] == "Invalid token"


def test_refresh_succeeds_without_touching_the_delete_cookies(client):
    user = SimpleNamespace(id=_USER_ID, github_login="octocat", avatar_url=None)
    session = SimpleNamespace(
        access_token="new-access", refresh_token="new-refresh", user=user
    )
    with patch("app.routers.auth.rotate_session", new=AsyncMock(return_value=session)):
        res = client.post("/auth/refresh")

    assert res.status_code == 200
    # 正常系では新しいトークンが発行され、削除Cookieは refresh_token では出ない
    assert any(
        "new-refresh" in c and "Path=/api/auth" in c
        for c in res.headers.get_list("set-cookie")
    )
    assert _refresh_cookie_paths(res) == {"/"}


def test_callback_accepts_matching_state_and_sets_refresh_cookie(client):
    client.cookies.set("github_oauth_state", "expected-state")

    with patch(
        "app.routers.auth.login_with_github_code",
        new=AsyncMock(return_value="issued-refresh-token"),
    ) as login:
        res = client.get("/auth/github/callback?code=abc&state=expected-state")

    login.assert_awaited_once()
    assert res.headers["location"].endswith("/auth/callback")
    refresh_cookie = next(
        c
        for c in res.headers.get_list("set-cookie")
        if "issued-refresh-token" in c
    )
    assert "HttpOnly" in refresh_cookie
    assert "Path=/api/auth" in refresh_cookie
    # 再ログインで復帰したときに旧Cookieが残ると refresh が壊れ続ける
    assert any(
        'refresh_token=""' in c and "Path=/;" in c
        for c in res.headers.get_list("set-cookie")
    )
