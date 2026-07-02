import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

from app.models.project import Project
from app.services.github import STALE_SYNC_THRESHOLD, _is_syncing


def test_is_syncing_uses_started_timestamp_even_when_flag_is_false():
    project = Project(
        name="demo",
        repo_owner="octo",
        repo_name="demo",
        weight_activity=40,
        weight_speed=35,
        weight_quality=25,
    )
    now = datetime.now(timezone.utc)

    project.github_syncing_started_at = now
    assert _is_syncing(project, now) is True

    project.github_syncing_started_at = now - STALE_SYNC_THRESHOLD - timedelta(seconds=1)
    assert _is_syncing(project, now) is False
