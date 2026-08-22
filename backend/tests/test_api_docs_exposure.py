"""APIドキュメント（Swagger UI / ReDoc / OpenAPI JSON）の公開判定。

認証が無く全エンドポイントの仕様が読めるため、公開環境で開いたままにしない。
設定の取り違えで静かに開くことがないよう、判定と FastAPI への配線の両方を固定する。
"""

import importlib

import pytest

from app import main
from app.core.config import settings


@pytest.mark.parametrize(
    ("expose", "frontend_url", "expected"),
    [
        # 明示指定は常に優先する（審査・デモで公開環境でも開けられる）
        (True, "https://vallog.example", True),
        (False, "http://localhost:3000", False),
        # 未指定なら FRONTEND_URL のスキームで決める
        (None, "http://localhost:3000", True),
        (None, "https://vallog.example", False),
    ],
)
def test_api_docs_enabled(monkeypatch, expose, frontend_url, expected):
    monkeypatch.setattr(settings, "expose_api_docs", expose)
    monkeypatch.setattr(settings, "frontend_url", frontend_url)
    assert main.api_docs_enabled() is expected


def test_docs_routes_absent_when_disabled(monkeypatch):
    """判定だけでなく、FastAPI に実際にルートが生えないことまで確認する。"""
    monkeypatch.setattr(settings, "expose_api_docs", False)
    try:
        reloaded = importlib.reload(main)
        paths = {route.path for route in reloaded.app.routes}
        assert "/docs" not in paths
        assert "/redoc" not in paths
        assert "/openapi.json" not in paths
        # 疎通確認に使う /health は閉じない（scripts/deploy.sh が参照する）
        assert "/health" in paths
    finally:
        # 他のテストは関数内で app を import し直すため、既定設定で組み直しておく
        monkeypatch.undo()
        importlib.reload(main)


def test_docs_routes_present_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "expose_api_docs", True)
    try:
        reloaded = importlib.reload(main)
        paths = {route.path for route in reloaded.app.routes}
        assert "/docs" in paths
        assert "/openapi.json" in paths
    finally:
        monkeypatch.undo()
        importlib.reload(main)
