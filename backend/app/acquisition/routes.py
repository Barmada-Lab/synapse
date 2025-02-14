from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from prefect.blocks.notifications import SlackWebhook
from sqlmodel import func, select

from app.core.deps import SessionDep
from app.labware.models import Wellplate
from app.users.deps import CurrentActiveUserDep

from . import crud
from .events import handle_plateread_status_update
from .models import (
    Acquisition,
    AcquisitionCreate,
    AcquisitionList,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    AcquisitionPlanRecord,
    AcquisitionRecord,
    AnalysisPlan,
    AnalysisPlanCreate,
    AnalysisPlanRecord,
    Instrument,
    InstrumentCreate,
    InstrumentList,
    InstrumentRecord,
    InstrumentType,
    InstrumentTypeCreate,
    InstrumentTypeList,
    InstrumentTypeRecord,
    OverlordAlert,
    PlatereadSpec,
    PlatereadSpecRecord,
    PlatereadSpecUpdate,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecCreate,
    SBatchAnalysisSpecRecord,
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

    instrument = session.get(Instrument, acquisition_create.instrument_id)
    if instrument is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No corresponding instrument found.",
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
    session: SessionDep, analysis_plan_create: AnalysisPlanCreate
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


@api_router.get(
    "/analysis_plans/{id}",
    response_model=AnalysisPlanRecord,
)
def get_analysis_plan(session: SessionDep, id: int) -> AnalysisPlanRecord:
    analysis_plan = session.get(AnalysisPlan, id)
    if not analysis_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis plan not found."
        )
    return AnalysisPlanRecord.model_validate(analysis_plan)


@api_router.delete("/analysis_plans/{id}")
def delete_analysis_plan(session: SessionDep, id: int) -> Response:
    analysis_plan = session.get(AnalysisPlan, id)
    if not analysis_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis plan not found."
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Analysis plan not found.",
        )
    spec = crud.create_analysis_spec(session=session, create=spec_create)
    return SBatchAnalysisSpecRecord.model_validate(spec)


@api_router.delete("/analyses/{analysis_id}")
def delete_sbatch_analysis_spec(session: SessionDep, analysis_id: int) -> Response:
    analysis = session.get(SBatchAnalysisSpec, analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis specification not found.",
        )
    session.delete(analysis)
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
    session: SessionDep,
    id: int,
    plateread_in: PlatereadSpecUpdate,
    background_tasks: BackgroundTasks,
) -> PlatereadSpecRecord:
    plateread_db = session.get(PlatereadSpec, id)
    if plateread_db is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plate-read not found"
        )

    status_updated = plateread_db.status != plateread_in.status
    crud.update_plateread(
        session=session, db_plateread=plateread_db, plateread_in=plateread_in
    )

    if status_updated:
        background_tasks.add_task(
            handle_plateread_status_update,
            plateread_db.id,  # type: ignore[arg-type]
            plateread_db.status,
        )

    return PlatereadSpecRecord.model_validate(plateread_db)


@api_router.post(
    "/instrument_types",
    response_model=InstrumentTypeRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_instrument_type(
    session: SessionDep, instrument_type_create: InstrumentTypeCreate
) -> InstrumentTypeRecord:
    instrument_type = crud.create_instrument_type(
        session=session, instrument_type_create=instrument_type_create
    )
    return InstrumentTypeRecord.model_validate(instrument_type)


@api_router.get("/instrument_types", response_model=InstrumentTypeList)
def get_instrument_types(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> InstrumentTypeList:
    count_statement = select(func.count()).select_from(InstrumentType)
    count = session.exec(count_statement).one()
    statement = select(InstrumentType).offset(skip).limit(limit)
    instrument_types = session.exec(statement).all()
    return InstrumentTypeList(data=instrument_types, count=count)


@api_router.delete("/instrument_types/{id}")
def delete_instrument_type(session: SessionDep, id: int) -> Response:
    instrument_type = session.get(InstrumentType, id)
    if not instrument_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instrument type not found"
        )
    session.delete(instrument_type)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post(
    "/instruments", response_model=InstrumentRecord, status_code=status.HTTP_201_CREATED
)
def create_instrument(
    session: SessionDep, instrument_create: InstrumentCreate
) -> InstrumentRecord:
    instrument = crud.create_instrument(
        session=session, instrument_create=instrument_create
    )
    return InstrumentRecord.model_validate(instrument)


@api_router.get("/instruments", response_model=InstrumentList)
def get_instruments(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> InstrumentList:
    count_statement = select(func.count()).select_from(Instrument)
    count = session.exec(count_statement).one()
    statement = select(Instrument).offset(skip).limit(limit)
    instruments = session.exec(statement).all()
    return InstrumentList(data=instruments, count=count)


@api_router.delete("/instruments/{id}")
def delete_instrument(session: SessionDep, id: int) -> Response:
    instrument = session.get(Instrument, id)
    if not instrument:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found"
        )
    session.delete(instrument)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post("/alerts")
def alert_overlord_error(alert: OverlordAlert) -> Response:
    # prefect was written by monkeys so these type definitions are completely fucked
    slack_webhook = SlackWebhook.load("tmnl-slack-webhook")  # type: ignore
    slack_webhook.notify(alert.message)  # type: ignore
    return Response(status_code=status.HTTP_204_NO_CONTENT)
