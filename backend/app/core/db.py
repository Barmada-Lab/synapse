from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.users import crud
from app.users.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    super_user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not super_user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        super_user = crud.create_user(session=session, user_create=user_in)

    overlord_user = session.exec(
        select(User).where(User.email == settings.OVERLORD_USER)
    ).first()
    if not overlord_user:
        user_in = UserCreate(
            email=settings.OVERLORD_USER,
            password=settings.OVERLORD_PASSWORD,
            is_superuser=True,
        )
        overlord_user = crud.create_user(session=session, user_create=user_in)
