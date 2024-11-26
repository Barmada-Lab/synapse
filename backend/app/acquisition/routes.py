from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import SessionDep
from app.labware.models import Wellplate
from app.users.deps import CurrentActiveUserDep

from . import crud
from .events import emit_plateread_status_update
from .models import (
    Acquisition,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    AcquisitionPlanRecord,
    PlatereadSpec,
    PlatereadSpecRecord,
    PlatereadSpecUpdate,
)

api_router = APIRouter(dependencies=[CurrentActiveUserDep])


@api_router.post(
    "/plans", response_model=AcquisitionPlanRecord, status_code=status.HTTP_201_CREATED
)
def create_acquisition_plan(
    session: SessionDep, plan_create: AcquisitionPlanCreate
) -> AcquisitionPlanRecord:
    if session.get(Wellplate, plan_create.wellplate_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No corresponding wellplate found.",
        )
    acquisition = session.get(Acquisition, plan_create.acquisition_id)
    if acquisition is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No corresponding acquisition found.",
        )
    elif acquisition.acquisition_plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Acquisition already has an acquisition plan.",
        )
    plan = crud.create_acquisition_plan(session=session, plan_create=plan_create)
    return AcquisitionPlanRecord.model_validate(plan)


@api_router.delete("/plans/{id}")
def delete_acquisition_plan(session: SessionDep, id: int) -> Response:
    plan = session.get(AcquisitionPlan, id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )
    session.delete(plan)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.patch(
    "/reads/{id}",
    response_model=PlatereadSpecRecord,
)
def update_plateread(
    session: SessionDep, id: int, plateread_in: PlatereadSpecUpdate
) -> PlatereadSpecRecord:
    plateread_db = session.get(PlatereadSpec, id)
    if plateread_db is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plate-read not found"
        )

    original_status = plateread_db.status
    crud.update_plateread(
        session=session, db_plateread=plateread_db, plateread_in=plateread_in
    )

    if original_status != plateread_db.status:
        emit_plateread_status_update(plateread=plateread_db, before=plateread_db.status)

    return PlatereadSpecRecord.model_validate(plateread_db)
