from cryptography.fernet import Fernet
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.config import settings


class EncryptedString(TypeDecorator):
    """DBに暗号化して保存するString型。読み書き時に自動で暗号化/復号する。"""

    impl = String
    cache_ok = True

    def _fernet(self) -> Fernet:
        return Fernet(settings.encryption_key.encode())

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self._fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self._fernet().decrypt(value.encode()).decode()
