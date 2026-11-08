"""Password hashing, JWT access tokens, refresh tokens and data encryption."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=64)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_b64, dk_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes), "typ": "access"}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        data = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data.get("sub") if data.get("typ") == "access" else None


def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().data_encryption_key
    if not key:
        if get_settings().environment == "production":
            raise RuntimeError("BID_DATA_ENCRYPTION_KEY must be set in production")
        # Deterministic dev key derived from the JWT secret so local data stays readable between restarts.
        key = base64.urlsafe_b64encode(hashlib.sha256(("dev:" + get_settings().jwt_secret).encode()).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken as e:  # pragma: no cover - indicates key mismatch / tampering
        raise RuntimeError("Encrypted data could not be decrypted (wrong key or tampered file)") from e


def encrypt_str(value: str) -> str:
    return encrypt_bytes(value.encode()).decode() if value else ""


def decrypt_str(value: str) -> str:
    return decrypt_bytes(value.encode()).decode() if value else ""
