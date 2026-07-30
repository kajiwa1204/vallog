"""認証セッション（リフレッシュトークンのローテーション）と OAuth state 検証のテスト。

DBは使わず、RefreshTokenRepository をインメモリのフェイクに差し替えて
services/auth.py の判定ロジックだけを検証する。
"""

import uuid
from datetime import datetime, timedelta, timezone
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
from app.services.auth import REFRESH_ROTATION_GRACE, rotate_session

_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class FakeRefreshTokenRepo:
    """RefreshTokenRepository のインメモリ版。コミットは呼び出し側の責務なので持たない。"""

    def __init__(self, tokens: list[RefreshToken] | None = None):
        self.rows: dict[uuid.UUID, RefreshToken] = {t.jti: t for t in tokens or []}

    async def create(self, *, jti, user_id, expires_at):
        row = RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at)
        self.rows[jti] = row
        return row

    async def get_by_jti(self, jti):
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
            self.rows[old_jti].replaced_by_jti = new_jti
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
        replaced_by_jti=None,
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


async def test_rotate_revokes_old_token_and_links_successor():
    row = _live_token()
    repo = FakeRefreshTokenRepo([row])

    session = await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    _, new_jti = decode_refresh_token(session.refresh_token)
    assert row.revoked_at is not None
    assert row.replaced_by_jti == new_jti
    assert repo.rows[new_jti].revoked_at is None


async def test_concurrent_refresh_within_grace_returns_successor():
    """複数タブが同じ旧トークンを送っても、強制ログアウトさせず後継を返す。"""
    row = _live_token()
    repo = FakeRefreshTokenRepo([row])
    old_token = create_refresh_token(_USER_ID, row.jti)

    first = await _rotate(repo, old_token)
    _, successor_jti = decode_refresh_token(first.refresh_token)

    # 2枚目のタブが、Set-Cookie が届く前に読んだ旧トークンで再送してくる
    second = await _rotate(repo, old_token)

    _, second_jti = decode_refresh_token(second.refresh_token)
    assert second_jti == successor_jti
    assert repo.rows[successor_jti].revoked_at is None


async def test_reuse_after_grace_period_revokes_every_token():
    successor = _live_token()
    row = _live_token(
        revoked_at=datetime.now(timezone.utc) - REFRESH_ROTATION_GRACE - timedelta(seconds=1),
        replaced_by_jti=successor.jti,
    )
    repo = FakeRefreshTokenRepo([row, successor])

    with pytest.raises(AppError) as exc:
        await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    assert exc.value.code == ErrorCode.AUTH_TOKEN_REUSE_DETECTED
    assert successor.revoked_at is not None


async def test_reuse_revokes_every_token_when_successor_already_rotated():
    """世代が進んだ後に古いトークンが出てきたら盗用と見なす。"""
    successor = _live_token(revoked_at=datetime.now(timezone.utc))
    row = _live_token(
        revoked_at=datetime.now(timezone.utc), replaced_by_jti=successor.jti
    )
    repo = FakeRefreshTokenRepo([row, successor])

    with pytest.raises(AppError) as exc:
        await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    assert exc.value.code == ErrorCode.AUTH_TOKEN_REUSE_DETECTED


async def test_revoked_token_without_successor_is_reuse():
    row = _live_token(revoked_at=datetime.now(timezone.utc))
    repo = FakeRefreshTokenRepo([row])

    with pytest.raises(AppError) as exc:
        await _rotate(repo, create_refresh_token(_USER_ID, row.jti))

    assert exc.value.code == ErrorCode.AUTH_TOKEN_REUSE_DETECTED


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
