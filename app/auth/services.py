import hashlib
import secrets
from datetime import datetime, timezone

from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db
from app.models import User, TrustScore, StudentProfile
from app.core.security import hash_password, verify_password


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="campus-os-auth")


def create_user(*, email: str, password: str, display_name: str, phone: str | None = None) -> User:
    email = email.strip().lower()
    user = User(
        email=email,
        phone=phone or None,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role="student",
        status="active",
    )
    user.trust = TrustScore()
    db.session.add(user)
    db.session.flush()  # get ID before optional profile creation
    return user


def authenticate(email: str, password: str) -> User | None:
    user = User.query.filter_by(email=email.strip().lower()).first()
    if not user or user.is_deleted or user.status != "active":
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    return user


def issue_reset_token(user: User) -> str:
    return _serializer().dumps({"uid": user.id})


def consume_reset_token(token: str, max_age: int = 3600) -> User | None:
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return User.query.get(data.get("uid"))


def set_password(user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)