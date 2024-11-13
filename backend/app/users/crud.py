from sqlmodel import Session, select

from app.core.security import create_api_key, get_secret_hash, verify_secret

from .models import (
    Application,
    ApplicationCreate,
    ApplicationKey,
    User,
    UserCreate,
    UserUpdate,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_secret_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_secret_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_secret(password, db_user.hashed_password):
        return None
    return db_user


def create_application(
    *, session: Session, user: User, application_create: ApplicationCreate
) -> ApplicationKey:
    key = create_api_key()
    model_dump = {"user_id": user.id, **application_create.model_dump()}
    db_app = Application.model_validate(
        model_dump, update={"hashed_key": get_secret_hash(key)}
    )
    session.add(db_app)
    session.commit()
    session.refresh(db_app)
    return ApplicationKey.model_validate(db_app, update={"key": key})
