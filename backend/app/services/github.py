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

    async def _request(self, path: str, params: dict | None = None) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                res = await client.get(f"{GITHUB_API}{path}", params=params, headers=self._headers)
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
        if res.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub APIの認証に失敗しました。再ログインしてください。",
            )
        if res.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub APIへのアクセスが拒否されました。レート制限に達している場合は、しばらくしてから再度お試しください。",
            )
        return res

    async def get_repo(self, owner: str, name: str) -> dict | None:
        res = await self._request(f"/repos/{owner}/{name}")
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    async def list_viewer_repos(self) -> list[dict]:
        """最大500件（5ページ）取得して返す。"""
        repos: list[dict] = []
        for page in range(1, 6):
            res = await self._request(
                "/user/repos",
                {"sort": "pushed", "affiliation": "owner,collaborator,organization_member", "per_page": 100, "page": page},
            )
            res.raise_for_status()
            page_items = res.json()
            repos.extend(page_items)
            if len(page_items) < 100:
                break
        return repos

    async def get_contributors(self, owner: str, name: str) -> list[dict]:
        res = await self._request(f"/repos/{owner}/{name}/contributors", {"per_page": 100})
        if res.status_code == 204:
            return []
        res.raise_for_status()
        return res.json()
