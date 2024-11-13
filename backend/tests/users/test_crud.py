import pytest
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.security import verify_secret
from app.users import crud
from app.users.models import (
    Application,
    ApplicationCreate,
    User,
    UserCreate,
    UserUpdate,
)
from tests.utils import create_random_user, random_email, random_lower_string


def test_create_user(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.email == email
    assert hasattr(user, "hashed_password")


def test_create_user_already_exists(db: Session) -> None:
    user = create_random_user(session=db)
    user_in = UserCreate(email=user.email, password=random_lower_string())
    with pytest.raises(IntegrityError):
        crud.create_user(session=db, user_create=user_in)
    db.rollback()


def test_authenticate_user(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    authenticated_user = crud.authenticate(session=db, email=email, password=password)
    assert authenticated_user
    assert user.email == authenticated_user.email


def test_not_authenticate_user(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user = crud.authenticate(session=db, email=email, password=password)
    assert user is None


def test_check_if_user_is_active(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_active is True


def test_check_if_user_is_active_inactive(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, is_active=False)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_active is False


def test_check_if_user_is_superuser(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_superuser is True


def test_check_if_user_is_superuser_normal_user(db: Session) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_superuser is False


def test_get_user(db: Session) -> None:
    password = random_lower_string()
    username = random_email()
    user_in = UserCreate(email=username, password=password, is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(db: Session) -> None:
    password = random_lower_string()
    email = random_email()
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    new_password = random_lower_string()
    user_in_update = UserUpdate(password=new_password, is_superuser=True)
    if user.id is not None:
        crud.update_user(session=db, db_user=user, user_in=user_in_update)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.email == user_2.email
    assert verify_secret(new_password, user_2.hashed_password)


def test_create_application(db: Session) -> None:
    user = create_random_user(session=db)
    app_create = ApplicationCreate(name=random_lower_string())
    app_key = crud.create_application(
        session=db, user=user, application_create=app_create
    )
    app = db.get(Application, app_key.id)
    assert app is not None
    assert verify_secret(app_key.key, app.hashed_key)


def test_delete_application(db: Session) -> None:
    user = create_random_user(session=db)
    app_create = ApplicationCreate(name=random_lower_string())
    app_key = crud.create_application(
        session=db, user=user, application_create=app_create
    )
    app = db.get(Application, app_key.id)
    assert app is not None
    db.delete(app)
    db.commit()
    assert db.get(Application, app.id) is None


def test_delete_user_app_cascade(db: Session) -> None:
    user = create_random_user(session=db)
    app_create = ApplicationCreate(name=random_lower_string())
    app_key = crud.create_application(
        session=db, user=user, application_create=app_create
    )
    app = db.get(Application, app_key.id)
    assert app is not None
    db.delete(user)
    db.commit()
    assert db.get(User, user.id) is None
    assert db.get(Application, app.id) is None
