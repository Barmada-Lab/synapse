import random
import string

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.users.crud import create_user
from app.users.models import UserCreate


def random_lower_string(k: int = 32) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=k))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def create_random_user(*, session: Session, **kwargs):
    kwargs.setdefault("email", random_email())
    kwargs.setdefault("password", random_lower_string())
    kwargs.setdefault("is_superuser", False)
    kwargs.setdefault("is_active", True)
    kwargs.setdefault("full_name", random_lower_string())
    user_in = UserCreate(**kwargs)
    user = create_user(session=session, user_create=user_in)
    return user


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


def get_superuser_api_key_headers(client: TestClient) -> dict[str, str]:
    token_headers = get_superuser_token_headers(client)
    application_create = {"name": random_lower_string()}
    response = client.post(
        headers=token_headers,
        url=f"{settings.API_V1_STR}/users/me/applications",
        json=application_create,
    )
    api_id = response.json()["id"]
    api_key = response.json()["key"]
    return {
        "x-api-id": api_id,
        "x-api-key": api_key
    }
