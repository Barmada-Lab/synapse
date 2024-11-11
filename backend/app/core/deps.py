from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.core.db import engine


def get_db() -> Session:
    return Session(engine)


def get_db_gen() -> Generator[Session, None, None]:
    with get_db() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db_gen)]
