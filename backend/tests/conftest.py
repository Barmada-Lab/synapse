from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from tests.users.utils import authentication_token_from_email
from tests.utils import get_superuser_token_headers, get_superuser_api_key_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        meta = SQLModel.metadata
        for table in reversed(meta.sorted_tables):
            statement = delete(table)
            session.execute(statement)
        init_db(session)
        session.commit()


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="session")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )

@pytest.fixture(scope="session")
def superuser_api_key_headers(client: TestClient):
    return get_superuser_api_key_headers(client)


@pytest.fixture(scope="session")
def unauthenticated_client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def pw_authenticated_client(
    normal_user_token_headers: dict[str, str],
) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        c.headers.update(normal_user_token_headers)
        yield c


@pytest.fixture(scope="session")
def key_authenticated_client(
    superuser_api_key_headers: dict[str, str],
) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        c.headers.update(superuser_api_key_headers)
        yield c
