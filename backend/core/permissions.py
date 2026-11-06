"""Ownership verification and quota deduction dependencies."""
from __future__ import annotations

import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.schemas import JobManifest
from backend.models.user import User, UserQuota


def verify_job_owner(manifest: JobManifest, current_user: User) -> None:
    """Ensure the authenticated user owns this job if an owner was recorded."""
    if current_user.role == "admin":
        return

    if manifest.user_id and str(manifest.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access or modify this job.",
        )


def check_and_consume_quota(current_user: User, db: Session, cost: int = 1) -> UserQuota:
    """Verify the user has sufficient credits and deduct them upon starting a processing job."""
    quota = db.query(UserQuota).filter(UserQuota.user_id == current_user.id).first()
    if not quota:
        quota = UserQuota(user_id=current_user.id, credit_allowance=3, credits_used=0)
        db.add(quota)
        db.flush()

    if current_user.role != "admin" and (quota.credits_used + cost > quota.credit_allowance):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Beta credits exhausted ({quota.credits_used}/{quota.credit_allowance} used). Contact an administrator for more credits.",
        )

    quota.credits_used += cost
    db.commit()
    return quota


def refund_quota(user_id: str | uuid.UUID | User, db: Session, cost: int = 1) -> UserQuota | None:
    """Refunds credits to the user if a processing job fails due to an internal error."""
    uid = user_id.id if isinstance(user_id, User) else user_id
    if isinstance(uid, str):
        try:
            uid = uuid.UUID(uid)
        except ValueError:
            return None

    quota = db.query(UserQuota).filter(UserQuota.user_id == uid).first()
    if not quota:
        return None

    quota.credits_used = max(0, quota.credits_used - cost)
    db.commit()
    db.refresh(quota)
    return quota
