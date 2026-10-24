"""Script to create or promote an admin user in the database."""
import argparse
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from backend.core.database import SessionLocal
from backend.core.security import hash_password
from backend.models.user import User, UserQuota


def create_or_update_admin(email: str, password: str, credits: int = 100):
    db = SessionLocal()
    try:
        email = email.lower().strip()
        user = db.query(User).filter(User.email == email).first()
        hashed = hash_password(password)

        if user:
            print(f"User {email} already exists. Updating to admin...")
            user.hashed_password = hashed
            user.role = "admin"
            user.status = "active"
        else:
            print(f"Creating new admin user {email}...")
            user = User(
                email=email,
                hashed_password=hashed,
                role="admin",
                status="active",
                token_version=1,
            )
            db.add(user)
            db.flush()

        quota = db.query(UserQuota).filter(UserQuota.user_id == user.id).first()
        if not quota:
            quota = UserQuota(user_id=user.id, credit_allowance=credits, credits_used=0)
            db.add(quota)
        else:
            quota.credit_allowance = max(quota.credit_allowance, credits)

        db.commit()
        print(f"Admin account successfully configured for: {email}")
        print(f"Role: {user.role}, Status: {user.status}, Credit Allowance: {quota.credit_allowance}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update an admin user.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--credits", type=int, default=100, help="Initial credit allowance (default: 100)")
    args = parser.parse_args()

    create_or_update_admin(args.email, args.password, args.credits)
