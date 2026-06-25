import httpx
from fastapi import status

from app.core.config import settings
from app.core.errors import AppError, ErrorCode

_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


async def fetch_github_access_token(code: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                _GITHUB_TOKEN_URL,
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
        data = res.json()
    except httpx.TimeoutException as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_TIMEOUT,
            "Connection to GitHub timed out",
        ) from e
    except (httpx.HTTPError, ValueError) as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_UNAVAILABLE,
            "Failed to connect to GitHub",
        ) from e

    token = data.get("access_token")
    if not token:
        error = data.get("error") or "unknown_error"
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            ErrorCode.GITHUB_TOKEN_EXCHANGE_FAILED,
            f"Failed to obtain GitHub access token: {error}",
        )
    return token


async def fetch_github_user(access_token: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                _GITHUB_USER_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if res.status_code != 200:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                ErrorCode.GITHUB_USER_FETCH_FAILED,
                "Failed to fetch GitHub user info",
            )
        return res.json()
    except httpx.TimeoutException as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_TIMEOUT,
            "Connection to GitHub timed out",
        ) from e
    except httpx.HTTPError as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_UNAVAILABLE,
            "Failed to connect to GitHub",
        ) from e
    except ValueError as e:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            ErrorCode.GITHUB_INVALID_RESPONSE,
            "Received an invalid response from GitHub",
        ) from e
