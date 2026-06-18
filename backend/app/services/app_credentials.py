from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.app_credential import AppCredential


def _fernet() -> Fernet:
    return Fernet(settings.encryption_key.encode())


async def get_github_credentials(
    db: AsyncSession,
) -> tuple[str, str] | None:
    """GitHub OAuth資格情報を解決して (client_id, client_secret) を返す。

    envに両方設定されていればenv優先（後方互換）。
    なければDBのapp_credentialsから読む。どちらも未設定ならNone。
    """
    if settings.github_client_id and settings.github_client_secret:
        return settings.github_client_id, settings.github_client_secret

    row = await db.scalar(select(AppCredential))
    if row is None:
        return None

    secret = _fernet().decrypt(row.github_client_secret_encrypted.encode()).decode()
    return row.github_client_id, secret


async def is_configured(db: AsyncSession) -> bool:
    """GitHub OAuth設定済みかどうかを返す。"""
    if settings.github_client_id and settings.github_client_secret:
        return True
    row = await db.scalar(select(AppCredential))
    return row is not None


async def save_github_credentials(
    db: AsyncSession, client_id: str, client_secret: str
) -> None:
    """資格情報をDB保存する。client_secretはFernet暗号化して保存する。

    呼び出し前に is_configured() で未設定を確認すること（409ガードは router で行う）。
    """
    encrypted = _fernet().encrypt(client_secret.encode()).decode()
    credential = AppCredential(
        github_client_id=client_id,
        github_client_secret_encrypted=encrypted,
    )
    db.add(credential)
    await db.commit()
