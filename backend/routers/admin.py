import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.auth import require_admin
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import generate_invite_token, hash_invite_token
from backend.models.schemas import InviteCreateRequest, InviteResponse
from backend.models.user import Invitation, User, UserQuota
from backend.models.project import Project
from backend.services.email import send_invite_email

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_admin_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all registered users, their roles, statuses, and credit usages."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    user_list = []
    for u in users:
        quota = db.query(UserQuota).filter(UserQuota.user_id == u.id).first()
        allowance = quota.credit_allowance if quota else 3
        used = quota.credits_used if quota else 0
        remaining = max(0, allowance - used)
        projects_count = db.query(Project).filter(Project.user_id == u.id).count()

        user_list.append({
            "id": str(u.id),
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "credit_allowance": allowance,
            "credits_used": used,
            "credits_remaining": remaining,
            "projects_count": projects_count,
            "created_at": u.created_at.isoformat(),
        })

    return {"users": user_list}


@router.get("/invites")
def list_admin_invites(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all invitations sent, their expiration, and acceptance state."""
    invites = db.query(Invitation).order_by(Invitation.created_at.desc()).all()
    invite_list = []
    now = datetime.now(timezone.utc)
    for inv in invites:
        is_accepted = inv.accepted_at is not None
        is_expired = not is_accepted and inv.expires_at < now

        invite_list.append({
            "id": str(inv.id),
            "email": inv.email,
            "expires_at": inv.expires_at.isoformat(),
            "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
            "created_at": inv.created_at.isoformat(),
            "status": "accepted" if is_accepted else ("expired" if is_expired else "pending"),
        })

    return {"invites": invite_list}


@router.post("/users/{user_id}/credits")
def update_user_credits(
    user_id: str,
    payload: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Adjust a user's credit allowance (e.g. increase quota)."""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID.")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    new_allowance = payload.get("credit_allowance")
    add_credits = payload.get("add_credits")

    quota = db.query(UserQuota).filter(UserQuota.user_id == user.id).first()
    if not quota:
        quota = UserQuota(user_id=user.id, credit_allowance=3, credits_used=0)
        db.add(quota)

    if new_allowance is not None:
        quota.credit_allowance = int(new_allowance)
    elif add_credits is not None:
        quota.credit_allowance += int(add_credits)

    db.commit()
    db.refresh(quota)

    return {
        "user_id": str(user.id),
        "credit_allowance": quota.credit_allowance,
        "credits_used": quota.credits_used,
        "credits_remaining": max(0, quota.credit_allowance - quota.credits_used),
    }


@router.post("/users/{user_id}/activate")
def activate_user(
    user_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reactivate a revoked user account."""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID.")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.status = "active"
    db.commit()
    return {"status": "active", "user_id": str(user.id)}


@router.post("/invites", response_model=InviteResponse)
def create_invite(
    payload: InviteCreateRequest,
    background_tasks: BackgroundTasks,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    raw_token = generate_invite_token()
    token_hash = hash_invite_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.invite_token_expire_days)

    invite = Invitation(
        email=payload.email.lower().strip(),
        invite_token_hash=token_hash,
        invited_by_user_id=admin_user.id,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()

    # Dispatch email via background task
    background_tasks.add_task(send_invite_email, invite.email, raw_token)

    return InviteResponse(
        email=invite.email,
        message="Invitation sent successfully via email.",
        expires_at=expires_at.isoformat(),
    )


@router.post("/users/{user_id}/revoke")
def revoke_user(
    user_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID.")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.status = "revoked"
    user.token_version += 1
    db.commit()

    return {"status": "revoked", "user_id": str(user.id)}
