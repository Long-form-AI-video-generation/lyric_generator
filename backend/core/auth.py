import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import decode_access_token
from backend.models.user import User

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Validate Bearer JWT token and fetch active user. Enforces immediate session revocation."""
    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise unauthorized_exception

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise unauthorized_exception

    user_id_raw = payload.get("sub")
    token_version = payload.get("token_version")

    if not user_id_raw or token_version is None:
        raise unauthorized_exception

    try:
        user_uuid = uuid.UUID(user_id_raw)
    except ValueError:
        raise unauthorized_exception

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise unauthorized_exception

    # Instant revocation check: If token_version was incremented, invalidate immediately
    if user.token_version != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account access is currently {user.status}.",
        )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures the current user has an admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required.",
        )
    return current_user
