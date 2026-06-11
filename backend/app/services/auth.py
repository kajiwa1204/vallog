import secrets
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_oauth_state_token, decode_token
from app.models import User
from app.repositories.user import UserRepository
from app.services.github import GitHubClient, exchange_oauth_code

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
# privateリポジトリのアクセス権確認・データ取得に repo スコープが必要
OAUTH_SCOPE = "repo read:user"


def build_authorize_url(invite_token: str | None) -> str:
    state = create_oauth_state_token(
        {"nonce": secrets.token_urlsafe(16), "invite": invite_token}
    )
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": f"{settings.frontend_url}/api/auth/github/callback",
        "scope": OAUTH_SCOPE,
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


async def handle_callback(
    db: AsyncSession, code: str, state: str
) -> tuple[User, str]:
    """OAuthコールバックを処理し、(ユーザー, リダイレクト先パス) を返す。"""
    claims = decode_token(state, "oauth_state")
    github_token = await exchange_oauth_code(code)
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
