from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from backend.app.core.config import get_settings


class CredentialCryptoError(RuntimeError):
    pass


class CredentialCipher:
    def __init__(self, key: str | None = None) -> None:
        self.key = key or get_settings().credential_encryption_key or self._dev_key()

    def encrypt_json(self, value: dict[str, Any]) -> str:
        fernet = self._fernet()
        payload = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        return fernet.encrypt(payload).decode("utf-8")

    def decrypt_json(self, token: str) -> dict[str, Any]:
        fernet = self._fernet()
        payload = fernet.decrypt(token.encode("utf-8"))
        return json.loads(payload.decode("utf-8"))

    def make_state(self, value: dict[str, Any]) -> str:
        return self.encrypt_json(value)

    def read_state(self, token: str) -> dict[str, Any]:
        return self.decrypt_json(token)

    def _fernet(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise CredentialCryptoError(
                "cryptography is required for encrypted credential storage. "
                "Install dependencies with `pip install -r requirements.txt`."
            ) from exc

        try:
            return Fernet(self.key.encode("utf-8"))
        except Exception as exc:
            raise CredentialCryptoError(
                "Invalid CREDENTIAL_ENCRYPTION_KEY. Generate one with "
                "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`."
            ) from exc

    @staticmethod
    def _dev_key() -> str:
        digest = hashlib.sha256(b"auto_upt-development-credential-key").digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8")
