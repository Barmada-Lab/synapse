from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import func, select

from app.core.deps import SessionDep
from app.users.deps import CurrentActiveUserDep

from . import crud
from .models import (
    AcquisitionPlan,
    AcquisitionPlanCreate,
    AcquisitionPlanList,
    AcquisitionPlanRecord,
    PlatereadSpec,
    PlatereadSpecRecord,
    PlatereadSpecUpdate,
)
from .utils import emit_plateread_status_update

api_router = APIRouter(dependencies=[CurrentActiveUserDep])


@api_router.get("/plans", response_model=AcquisitionPlanList)
def list_plans(
    session: SessionDep, skip: int = 0, limit: int = 100, name: str | None = None
) -> AcquisitionPlanList:
    # TODO: make this betta
    count_statement = select(func.count()).select_from(AcquisitionPlan)
    if name is not None:
        count_statement = count_statement.where(AcquisitionPlan.name == name)
    count = session.exec(count_statement).one()

    statement = select(AcquisitionPlan).offset(skip).limit(limit)
    if name is not None:
        statement = statement.where(AcquisitionPlan.name == name)
    plans = session.exec(statement).all()
    plan_records = [AcquisitionPlanRecord.model_validate(plan) for plan in plans]

    return AcquisitionPlanList(data=plan_records, count=count)


@api_router.post(
    "/plans", response_model=AcquisitionPlanRecord, status_code=status.HTTP_201_CREATED
)
def create_plan(
    session: SessionDep, plan_create: AcquisitionPlanCreate
) -> AcquisitionPlanRecord:
    if (
        crud.get_acquisition_plan_by_name(session=session, name=plan_create.name)
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A plan with this name already exists.",
        )
    plan = crud.create_acquisition_plan(session=session, plan_create=plan_create)
    return AcquisitionPlanRecord.model_validate(plan)


@api_router.delete("/plans/{id}")
def delete_plan_by_name(session: SessionDep, id: int) -> Response:
    plan = session.get(AcquisitionPlan, id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )
    session.delete(plan)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post("/plans/{id}/schedule", response_model=AcquisitionPlanRecord)
def schedule_acquisition_plan(session: SessionDep, id: int) -> AcquisitionPlanRecord:
    plan = session.get(AcquisitionPlan, id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )
    if plan.schedule != []:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This plan has already been scheduled",
        )
    plan = crud.schedule_plan(session=session, plan=plan)
    return AcquisitionPlanRecord.model_validate(plan)


@api_router.patch("/reads/{id}", response_model=PlatereadSpecRecord)
def update_plateread(
    session: SessionDep, id: int, plateread_in: PlatereadSpecUpdate
) -> PlatereadSpecRecord:
    plateread_db = session.get(PlatereadSpec, id)
    if plateread_db is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plate-read not found"
        )

    plateread_updated = crud.update_plateread(
        session=session, db_plateread=plateread_db, plateread_in=plateread_in
    )

    if plateread_db.status != plateread_updated.status:
        emit_plateread_status_update(
            plateread=plateread_updated, before=plateread_db.status
        )

    return PlatereadSpecRecord.model_validate(plateread_updated)
