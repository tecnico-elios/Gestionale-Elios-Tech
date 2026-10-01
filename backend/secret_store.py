"""Small server-side secret encryption helper for local settings.

Secrets are encrypted with a key derived from JWT_SECRET. The encrypted value can be
stored in MongoDB without exposing the plaintext to the frontend.
"""
from __future__ import annotations

import base64
import hashlib
import os
from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    seed = (os.environ.get("JWT_SECRET") or "elios-tech-local").encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def mask_secret(value: str) -> str:
    value = value or ""
    if not value:
        return ""
    return (value[:4] + "••••" + value[-4:]) if len(value) > 10 else "••••••••"
