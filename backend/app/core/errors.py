from enum import StrEnum

from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    """機械可読な安定したエラー識別子。フロントはこの code で文言を出し分ける。
    値は変更しない（契約）。文言（detail）は開発者向けなので自由に変えてよい。"""

    # 認証
    AUTH_NOT_AUTHENTICATED = "AUTH_NOT_AUTHENTICATED"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_USER_NOT_FOUND = "AUTH_USER_NOT_FOUND"
    AUTH_REFRESH_TOKEN_MISSING = "AUTH_REFRESH_TOKEN_MISSING"
    AUTH_TOKEN_REUSE_DETECTED = "AUTH_TOKEN_REUSE_DETECTED"
    # プロジェクト / メンバーシップ
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    PROJECT_FORBIDDEN = "PROJECT_FORBIDDEN"
    REPO_ALREADY_REGISTERED = "REPO_ALREADY_REGISTERED"
    REPO_NOT_FOUND = "REPO_NOT_FOUND"
    REPO_ACCESS_DENIED = "REPO_ACCESS_DENIED"
    # 招待
    INVITATION_NOT_FOUND = "INVITATION_NOT_FOUND"
    INVITATION_EXPIRED = "INVITATION_EXPIRED"
    # GitHub 連携（上流）
    GITHUB_TIMEOUT = "GITHUB_TIMEOUT"
    GITHUB_UNAVAILABLE = "GITHUB_UNAVAILABLE"
    GITHUB_AUTH_FAILED = "GITHUB_AUTH_FAILED"
    GITHUB_FORBIDDEN = "GITHUB_FORBIDDEN"
    GITHUB_RATE_LIMITED = "GITHUB_RATE_LIMITED"
    GITHUB_TOKEN_EXCHANGE_FAILED = "GITHUB_TOKEN_EXCHANGE_FAILED"
    GITHUB_USER_FETCH_FAILED = "GITHUB_USER_FETCH_FAILED"
    GITHUB_INVALID_RESPONSE = "GITHUB_INVALID_RESPONSE"
    # 貢献サマリー
    SUMMARY_PR_NOT_FOUND = "SUMMARY_PR_NOT_FOUND"


class AppError(Exception):
    """アプリ定義のエラー。レスポンスは {"detail", "code"} で返す。
    detail は開発者向けの英語メッセージ、code は機械可読な安定識別子。"""

    def __init__(self, status_code: int, code: ErrorCode, detail: str):
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code.value},
    )
