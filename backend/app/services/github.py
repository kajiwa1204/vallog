import httpx
from fastapi import HTTPException, status

GITHUB_API = "https://api.github.com"
_TIMEOUT = 30.0


class GitHubClient:
    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> httpx.Response:
        res = await client.get(f"{GITHUB_API}{path}", params=params, headers=self._headers)
        if res.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub APIの認証に失敗しました。再ログインしてください。",
            )
        return res

    async def get_repo(self, owner: str, name: str) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                res = await self._get(client, f"/repos/{owner}/{name}")
        except httpx.TimeoutException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub への接続がタイムアウトしました",
            ) from e
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub への接続に失敗しました",
            ) from e
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    async def list_viewer_repos(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                res = await self._get(
                    client,
                    "/user/repos",
                    {"sort": "pushed", "affiliation": "owner,collaborator,organization_member", "per_page": 100},
                )
        except httpx.TimeoutException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub への接続がタイムアウトしました",
            ) from e
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub への接続に失敗しました",
            ) from e
        res.raise_for_status()
        return res.json()

    async def get_contributors(self, owner: str, name: str) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                res = await self._get(client, f"/repos/{owner}/{name}/contributors", {"per_page": 100})
        except httpx.TimeoutException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub への接続がタイムアウトしました",
            ) from e
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub への接続に失敗しました",
            ) from e
        if res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub APIからエラーが返されました",
            )
        return res.json()
