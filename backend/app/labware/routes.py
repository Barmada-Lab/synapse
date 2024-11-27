from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from app.common.models import Message
from app.core.deps import SessionDep
from app.users.deps import CurrentActiveUserDep

from . import crud, flows
from .events import emit_wellplate_location_update
from .models import (
    Wellplate,
    WellplateCreate,
    WellplateList,
    WellplateRecord,
    WellplateUpdate,
)

api_router = APIRouter(dependencies=[CurrentActiveUserDep])


@api_router.get("/", response_model=WellplateList)
def list_wellplates(
    session: SessionDep, skip: int = 0, limit: int = 100, name: str | None = None
) -> WellplateList:
    count_statement = select(func.count()).select_from(Wellplate)
    if name is not None:
        count_statement = count_statement.where(Wellplate.name == name)
    count = session.exec(count_statement).one()

    statement = select(Wellplate).offset(skip).limit(limit)
    if name is not None:
        statement = statement.where(Wellplate.name == name)
    wellplates = session.exec(statement).all()

    return WellplateList(data=wellplates, count=count)


@api_router.post(
    "/",
    response_model=WellplateRecord,
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
    return WellplateRecord.model_validate(wellplate)


@api_router.patch(
    "/{wellplate_id}",
    response_model=WellplateRecord,
)
def update_wellplate_location(
    session: SessionDep,
    wellplate_id: int,
    wellplate_in: WellplateUpdate,
) -> WellplateRecord:
    if (wellplate := session.get(Wellplate, wellplate_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wellplate not found."
        )
    before_location = wellplate.location
    wellplate = crud.update_wellplate(
        session=session, db_wellplate=wellplate, wellplate_in=wellplate_in
    )

    if before_location != wellplate.location:
        emit_wellplate_location_update(wellplate=wellplate, before=before_location)

    return WellplateRecord.model_validate(wellplate)


@api_router.post(
    "/{wellplate_id}/barcode",
    response_model=Message,
)
def print_barcode(session: SessionDep, wellplate_id: int) -> Message:
    if (wellplate := session.get(Wellplate, wellplate_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wellplate not found."
        )
    barcode = wellplate.name
    try:
        flows.print_wellplate_barcode(barcode)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to print barcode: {e}",
        )
    return Message(message="Barcode printed.")
