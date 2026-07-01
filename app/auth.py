import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app import models


def hash_password(password: str) -> str:
    """We used simple PBKDF2 password hash for the assessment demo.

    For production replacement: company SSO/OAuth or a managed auth provider.
    """
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"{salt}${digest}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        salt, expected_digest = password_hash.split("$", 1)
    except ValueError:
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return hmac.compare_digest(actual_digest, expected_digest)


def get_current_user(request: Request, db: Session) -> Optional[models.User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(models.User).filter(models.User.id == int(user_id)).first()


def is_admin(user: models.User) -> bool:
    return bool(user and user.role == models.ROLE_ADMIN)


def is_auditor(user: models.User) -> bool:
    return bool(user and user.role == models.ROLE_AUDITOR)


def client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


def device_info(request: Request) -> str:
    return request.headers.get("user-agent", "unknown")[:255]
