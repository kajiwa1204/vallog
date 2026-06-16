import httpx
from fastapi import HTTPException, status

from app.core.config import settings

_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


async def fetch_github_access_token(code: str) -> str:
    async with httpx.AsyncClient() as client:
        res = await client.post(
            _GITHUB_TOKEN_URL,
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
    token = res.json().get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub access token の取得に失敗しました",
        )
    return token


async def fetch_github_user(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        res = await client.get(
            _GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub ユーザー情報の取得に失敗しました",
        )
    return res.json()
