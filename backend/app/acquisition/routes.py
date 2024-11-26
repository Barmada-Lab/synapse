from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import func, select

from app.core.deps import SessionDep
from app.labware.models import Wellplate
from app.users.deps import CurrentActiveUserDep

from . import crud
from .events import emit_plateread_status_update
from .models import (
    Acquisition,
    AcquisitionCreate,
    AcquisitionList,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    AcquisitionPlanRecord,
    AcquisitionRecord,
    AnalysisPlan,
    AnalysisPlanRecord,
    PlatereadSpec,
    PlatereadSpecRecord,
    PlatereadSpecUpdate,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecCreate,
    SBatchAnalysisSpecRecord,
    SBatchAnalysisSpecUpdate,
)

api_router = APIRouter(dependencies=[CurrentActiveUserDep])


@api_router.get("/acquisitions", response_model=AcquisitionList)
def get_acquisitions(session: SessionDep, skip: int = 0, limit: int = 100):
    count_statement = select(func.count()).select_from(Acquisition)
    count = session.exec(count_statement).one()

    statement = select(Acquisition).offset(skip).limit(limit)
    users = session.exec(statement).all()

    return AcquisitionList(data=users, count=count)


@api_router.post(
    "/acquisitions",
    response_model=AcquisitionRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_acquisition(
    session: SessionDep, acquisition_create: AcquisitionCreate
) -> AcquisitionRecord:
    if crud.get_acquisition_by_name(session=session, name=acquisition_create.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An acquisition with this name already exists.",
        )
    acquisition = crud.create_acquisition(
        session=session, acquisition_create=acquisition_create
    )
    return AcquisitionRecord.model_validate(acquisition)


@api_router.delete("/acquisitions/{id}")
def delete_acquisition(session: SessionDep, id: int) -> Response:
    acquisition = session.get(Acquisition, id)
    if not acquisition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Acquisition not found."
        )
    session.delete(acquisition)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post(
    "/analysis_plans",
    response_model=AnalysisPlanRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_analysis_plan(
    session: SessionDep, analysis_plan_create: AnalysisPlan
) -> AnalysisPlanRecord:
    acquisition_id = analysis_plan_create.acquisition_id
    acquisition = session.get(Acquisition, acquisition_id)
    if acquisition is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No corresponding acquisition found.",
        )
    elif acquisition.analysis_plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Acquisition already has an analysis plan.",
        )
    plan = crud.create_analysis_plan(session=session, acquisition_id=acquisition_id)
    return AnalysisPlanRecord.model_validate(plan)


@api_router.delete("/analysis_plans/{id}")
def delete_analysis_plan(session: SessionDep, id: int) -> Response:
    analysis_plan = session.get(AnalysisPlan, id)
    if not analysis_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found."
        )
    session.delete(analysis_plan)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post(
    "/analyses",
    response_model=SBatchAnalysisSpecRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_sbatch_analysis_spec(
    session: SessionDep, spec_create: SBatchAnalysisSpecCreate
) -> SBatchAnalysisSpecRecord:
    analysis_plan_id = spec_create.analysis_plan_id
    analysis_plan = session.get(AnalysisPlan, analysis_plan_id)
    if analysis_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found."
        )
    spec = crud.create_analysis_spec(
        session=session, analysis_plan_id=analysis_plan_id, create=spec_create
    )
    return SBatchAnalysisSpecRecord.model_validate(spec)


@api_router.patch(
    "/analyses/{id}",
    response_model=SBatchAnalysisSpecRecord,
)
def update_sbatch_analysis_spec(
    *, session: SessionDep, id: int, update: SBatchAnalysisSpecUpdate
) -> SBatchAnalysisSpecRecord:
    analysis_spec = session.get(SBatchAnalysisSpec, id)
    if analysis_spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis spec not found."
        )
    updated = crud.update_analysis_spec(
        session=session, db_analysis=analysis_spec, update=update
    )
    return SBatchAnalysisSpecRecord.model_validate(updated)


@api_router.delete("/analyses/{id}")
def delete_sbatch_analysis_spec(session: SessionDep, id: int) -> Response:
    spec = session.get(SBatchAnalysisSpec, id)
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Spec not found."
        )
    session.delete(spec)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post(
    "/acquisition_plans",
    response_model=AcquisitionPlanRecord,
    status_code=status.HTTP_201_CREATED,
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


@api_router.delete("/acquisition_plans/{id}")
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
    "/platereads/{id}",
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
