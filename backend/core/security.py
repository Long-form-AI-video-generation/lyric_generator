import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
import jwt
from backend.core.config import settings


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str, token_version: int, expires_delta: timedelta | None = None) -> str:
    """Generate a signed JWT token containing user_id and token_version."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "token_version": token_version,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.PyJWTError:
        return None


def generate_invite_token() -> str:
    """Generate a high-entropy URL-safe token to send to the invited user."""
    return secrets.token_urlsafe(32)


def hash_invite_token(raw_token: str) -> str:
    """Generate SHA-256 hash of the invite token for secure DB storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


