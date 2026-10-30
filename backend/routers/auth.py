from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.security import (
    create_access_token,
    hash_invite_token,
    hash_password,
    verify_password,
)
from backend.models.schemas import (
    AcceptInviteRequest,
    InviteVerifyResponse,
    LoginRequest,
    TokenResponse,
    UserProfileResponse,
)
from backend.models.user import Invitation, User, UserQuota

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Account is {user.status}.")

    token = create_access_token(user_id=str(user.id), token_version=user.token_version)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quota = db.query(UserQuota).filter(UserQuota.user_id == current_user.id).first()
    remaining = (quota.credit_allowance - quota.credits_used) if quota else 0
    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        status=current_user.status,
        credits_remaining=max(0, remaining),
    )


@router.get("/invites/verify", response_model=InviteVerifyResponse)
def verify_invite(token: str, db: Session = Depends(get_db)):
    token_hash = hash_invite_token(token)
    invitation = db.query(Invitation).filter(
        Invitation.invite_token_hash == token_hash,
        Invitation.accepted_at.is_(None),
    ).first()

    now = datetime.now(timezone.utc)
    if not invitation or invitation.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token is invalid or expired.")

    return InviteVerifyResponse(valid=True, email=invitation.email)


@router.post("/invites/accept", response_model=TokenResponse)
def accept_invite(payload: AcceptInviteRequest, db: Session = Depends(get_db)):
    token_hash = hash_invite_token(payload.token)
    invitation = db.query(Invitation).filter(
        Invitation.invite_token_hash == token_hash,
        Invitation.accepted_at.is_(None),
    ).first()

    now = datetime.now(timezone.utc)
    if not invitation or invitation.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token is invalid or expired.")

    existing_user = db.query(User).filter(User.email == invitation.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account already exists for this email.")

    # Create new user
    new_user = User(
        email=invitation.email,
        hashed_password=hash_password(payload.password),
        role="user",
        status="active",
        token_version=1,
    )
    db.add(new_user)
    db.flush()

    # Assign initial quota allowance (default 3 credits)
    quota = UserQuota(
        user_id=new_user.id,
        credit_allowance=3,
        credits_used=0,
    )
    db.add(quota)

    # Mark invitation as accepted
    invitation.accepted_at = now
    db.commit()
    db.refresh(new_user)

    token = create_access_token(user_id=str(new_user.id), token_version=new_user.token_version)
    return TokenResponse(access_token=token)


