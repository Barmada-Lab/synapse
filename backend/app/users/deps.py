from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError

from app.core import security
from app.core.config import settings
from app.core.deps import SessionDep

from .models import Application, TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token", auto_error=False
)
PWBearerDep = Annotated[str, Depends(reusable_oauth2)]


def check_oauth_bearer(session: SessionDep, token: PWBearerDep) -> User | None:
    if not token:
        return None

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
APIKeyDep = Annotated[str, Depends(api_key_header)]


def check_api_key(
    session: SessionDep, api_key: APIKeyDep, x_api_id: str | None = Header(default=None)
) -> User | None:
    if not api_key or not x_api_id:
        return None

    application = session.get(Application, x_api_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found"
        )
    elif not security.verify_secret(api_key, application.hashed_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    return application.user


def check_oauth_or_api_key(
    token_user: User | None = Depends(check_oauth_bearer),
    api_user: User | None = Depends(check_api_key),
) -> User | None:
    match (token_user, api_user):
        case (None, None):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )
        case (None, api_user):
            return api_user
        case (token_user, None):
            return token_user
        case _:  # fail if both users are present
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Use only one authentication method",
            )


CurrentUserDep = Depends(check_oauth_or_api_key)
CurrentUser = Annotated[User, CurrentUserDep]


def get_current_active_user(current_user: CurrentUser) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


CurrentActiveUserDep = Depends(get_current_active_user)
CurrentActiveUser = Annotated[User, CurrentActiveUserDep]


def get_current_active_superuser(current_user: CurrentActiveUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


CurrentActiveSuperuserDep = Depends(get_current_active_superuser)
CurrentActiveSuperuser = Annotated[User, CurrentActiveSuperuserDep]
