from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from app.core.deps import SessionDep
from app.users.deps import CurrentActiveUserDep

from . import crud
from .models import (
    Wellplate,
    WellplateCreate,
    WellplateList,
    WellplateRecord,
    WellplateUpdate,
)

api_router = APIRouter()


@api_router.get("/", response_model=WellplateList, dependencies=[CurrentActiveUserDep])
def read_wellplates(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> WellplateList:
    count_statement = select(func.count()).select_from(Wellplate)
    count = session.exec(count_statement).one()

    statement = select(Wellplate).offset(skip).limit(limit)
    wellplates = session.exec(statement).all()

    return WellplateList(data=wellplates, count=count)


@api_router.post(
    "/",
    response_model=WellplateRecord,
    dependencies=[CurrentActiveUserDep],
    status_code=status.HTTP_201_CREATED,
)
def create_wellplate(
    session: SessionDep, wellplate_in: WellplateCreate
) -> WellplateRecord:
    if crud.get_wellplate_by_name(session=session, name=wellplate_in.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A wellplate with this name already exists.",
        )
    wellplate = crud.create_wellplate(session=session, wellplate_create=wellplate_in)
    return wellplate


@api_router.patch(
    "/{wellplate_name}",
    response_model=WellplateRecord,
    dependencies=[CurrentActiveUserDep],
)
def update_wellplate(
    session: SessionDep,
    wellplate_name: str,
    wellplate_in: WellplateUpdate,
) -> WellplateRecord:
    if (
        wellplate := crud.get_wellplate_by_name(session=session, name=wellplate_name)
    ) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wellplate not found."
        )

    wellplate = crud.update_wellplate(
        session=session, db_wellplate=wellplate, wellplate_in=wellplate_in
    )
    return wellplate
