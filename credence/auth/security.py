"""Cryptographic security utilities for authentication and token management."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

# Configuration
SECRET_KEY = os.getenv("CREDENCE_SECRET_KEY", os.getenv("SECRET_KEY", "credence-dev-secret-key-change-in-production-4827103859"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with fallback."""
    try:
        return pwd_context.hash(password)
    except Exception:
        # PBKDF2-HMAC-SHA256 fallback if native bcrypt fails on some environments
        salt = secrets.token_hex(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return f"pbkdf2_sha256${salt}${h.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hash."""
    if hashed_password.startswith("pbkdf2_sha256$"):
        parts = hashed_password.split("$")
        if len(parts) == 3:
            salt = parts[1]
            target_hash = parts[2]
            computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            return hmac.compare_digest(target_hash, computed)
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None
