import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_secret(plain_secret: str, hashed_secret: str) -> bool:
    return pwd_context.verify(plain_secret, hashed_secret)


def get_secret_hash(secret: str) -> str:
    return pwd_context.hash(secret)


def create_api_key() -> str:
    return secrets.token_urlsafe(128)
