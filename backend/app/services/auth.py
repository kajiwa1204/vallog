import secrets
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_oauth_state_token, decode_token
from app.models import User
from app.repositories.user import UserRepository
from app.services.app_credentials import get_github_credentials
from app.services.github import GitHubClient

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
# privateリポジトリのアクセス権確認・データ取得に repo スコープが必要
OAUTH_SCOPE = "repo read:user"

_UNCONFIGURED_MSG = "GitHub OAuthが未設定です。セットアップを完了してください。"


async def build_authorize_url(db: AsyncSession, invite_token: str | None) -> str:
    creds = await get_github_credentials(db)
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_UNCONFIGURED_MSG,
        )
    client_id, _ = creds
    state = create_oauth_state_token(
        {"nonce": secrets.token_urlsafe(16), "invite": invite_token}
    )
    params = {
        "client_id": client_id,
        "redirect_uri": f"{settings.frontend_url}/api/auth/github/callback",
        "scope": OAUTH_SCOPE,
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


async def _exchange_code(
    client_id: str, client_secret: str, code: str
) -> str:
    """DBまたはenvから取得した資格情報でGitHub OAuthコードをトークンに交換する。"""
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            GITHUB_OAUTH_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        res.raise_for_status()
        payload = res.json()
    token = payload.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuthに失敗しました: {payload.get('error_description', 'unknown error')}",
        )
    return token


async def handle_callback(
    db: AsyncSession, code: str, state: str
) -> tuple[User, str]:
    """OAuthコールバックを処理し、(ユーザー, リダイレクト先パス) を返す。"""
    claims = decode_token(state, "oauth_state")

    creds = await get_github_credentials(db)
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_UNCONFIGURED_MSG,
        )
    client_id, client_secret = creds

    github_token = await _exchange_code(client_id, client_secret, code)
    gh_user = await GitHubClient(github_token).get_authenticated_user()

    user = await UserRepository(db).upsert_from_github(
        github_id=gh_user["id"],
        github_login=gh_user["login"],
        access_token=github_token,
        avatar_url=gh_user.get("avatar_url"),
    )
    await db.commit()

    invite = claims.get("invite")
    redirect_path = f"/invite/{invite}" if invite else "/projects"
    return user, redirect_path
