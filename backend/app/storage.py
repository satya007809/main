"""Encrypted object storage for case files and reports.

Every object is Fernet-encrypted (AES-128-CBC + HMAC) before it touches disk. The interface is
intentionally small so an S3/GCS backend with server-side KMS can replace LocalEncryptedStorage.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .config import get_settings
from .models import new_id
from .security import decrypt_bytes, encrypt_bytes


class LocalEncryptedStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if ".." in key or key.startswith("/"):
            raise ValueError("invalid storage key")
        return self.root / key

    def put(self, data: bytes, prefix: str) -> str:
        key = f"{prefix}/{new_id()}.bin"
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(encrypt_bytes(data))
        os.replace(tmp, p)
        return key

    def get(self, key: str) -> bytes:
        return decrypt_bytes(self._path(key).read_bytes())

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass

    def delete_prefix(self, prefix: str) -> None:
        shutil.rmtree(self._path(prefix), ignore_errors=True)


_storage: LocalEncryptedStorage | None = None


def get_storage() -> LocalEncryptedStorage:
    global _storage
    if _storage is None or str(_storage.root) != str(Path(get_settings().storage_dir)):
        _storage = LocalEncryptedStorage(get_settings().storage_dir)
    return _storage
