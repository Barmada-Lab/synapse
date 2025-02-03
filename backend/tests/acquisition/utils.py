import os
import random
import tempfile
from datetime import timedelta

from sqlmodel import Session

from app.acquisition.crud import (
    create_acquisition,
    create_acquisition_plan,
    create_analysis_plan,
    create_analysis_spec,
    create_artifact_collection,
    create_instrument,
    create_instrument_type,
)
from app.acquisition.models import (
    Acquisition,
    AcquisitionCreate,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    AnalysisPlan,
    AnalysisTrigger,
    ArtifactCollection,
    ArtifactCollectionCreate,
    ArtifactType,
    ImagingPriority,
    Instrument,
    InstrumentCreate,
    InstrumentType,
    InstrumentTypeCreate,
    ProcessStatus,
    Repository,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecCreate,
    Wellplate,
)
from app.labware.models import Location
from tests.labware.events import create_random_wellplate
from tests.utils import random_lower_string


def create_random_acquisition(*, session: Session, **kwargs) -> Acquisition:
    kwargs.setdefault("name", random_lower_string())
    if "instrument_id" not in kwargs:
        instrument = create_random_instrument(session=session)
        kwargs["instrument_id"] = instrument.id
    acquisition_create = AcquisitionCreate(
        name=kwargs["name"], instrument_id=kwargs["instrument_id"]
    )
    return create_acquisition(session=session, acquisition_create=acquisition_create)


def create_random_analysis_plan(
    *, session: Session, acquisition: Acquisition | None = None
) -> AnalysisPlan:
    if acquisition is None:
        acquisition = create_random_acquisition(session=session)
    return create_analysis_plan(
        session=session,
        acquisition_id=acquisition.id,  # type: ignore
    )


def create_random_analysis_spec(
    *,
    session: Session,
    analysis_trigger: AnalysisTrigger | None = None,
    trigger_value: int | None = None,
    acquisition: Acquisition | None = None,
) -> SBatchAnalysisSpec:
    analysis_plan = create_random_analysis_plan(
        session=session, acquisition=acquisition
    )
    if analysis_trigger is None:
        analysis_trigger = random.choice(list(AnalysisTrigger))
    analysis_create = SBatchAnalysisSpecCreate(
        trigger=analysis_trigger,
        trigger_value=trigger_value,
        analysis_cmd=random_lower_string(),
        analysis_args=[random_lower_string()],
        analysis_plan_id=analysis_plan.id,
    )
    return create_analysis_spec(
        session=session,
        create=analysis_create,
    )


def create_random_acquisition_plan(
    *,
    session: Session,
    acquisition: Acquisition | None = None,
    wellplate_id: int | None = None,
    **kwargs,
) -> AcquisitionPlan:
    kwargs.setdefault("name", random_lower_string())
    if acquisition is None:
        instrument = create_random_instrument(session=session)
        acquisition_create = AcquisitionCreate(
            name=kwargs["name"], instrument_id=instrument.id
        )
        acquisition = create_acquisition(
            session=session, acquisition_create=acquisition_create
        )

    if wellplate_id is None:
        wellplate = create_random_wellplate(session=session)
        wellplate_id = int(wellplate.id)

    kwargs.setdefault("wellplate_id", wellplate_id)
    kwargs.setdefault("storage_location", Location.CYTOMAT2)
    kwargs.setdefault("protocol_name", random_lower_string())
    kwargs.setdefault("n_reads", 1)
    kwargs.setdefault("interval", timedelta(minutes=1))
    kwargs.setdefault("deadline_delta", timedelta(minutes=1))
    kwargs.setdefault("priority", ImagingPriority.NORMAL)

    acquisition_plan = AcquisitionPlanCreate(
        acquisition_id=acquisition.id,
        wellplate_id=kwargs["wellplate_id"],
        storage_location=kwargs["storage_location"],
        protocol_name=kwargs["protocol_name"],
        n_reads=kwargs["n_reads"],
        interval=kwargs["interval"],
        deadline_delta=kwargs["deadline_delta"],
        priority=kwargs["priority"],
    )
    return create_acquisition_plan(session=session, plan_create=acquisition_plan)


def create_random_artifact_collection(
    *,
    session: Session,
    artifact_type: ArtifactType = ArtifactType.ACQUISITION_DATA,
    location: Repository = Repository.ACQUISITION_STORE,
    acquisition: Acquisition | None = None,
) -> ArtifactCollection:
    if acquisition is None:
        acquisition = create_random_acquisition(session=session)

    artifact_collection_create = ArtifactCollectionCreate(
        acquisition_id=acquisition.id, artifact_type=artifact_type, location=location
    )
    collection = create_artifact_collection(
        session=session,
        artifact_collection_create=artifact_collection_create,
    )
    collection.path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=collection.path, delete=False) as f:
        f.write(os.urandom(1024))
    return collection


def move_plate_to_acquisition_plan_location(
    wellplate: Wellplate, acquisition_plan: AcquisitionPlan, session: Session
):
    wellplate.location = acquisition_plan.storage_location
    session.add(wellplate)
    session.commit()
    session.refresh(acquisition_plan)
    return wellplate


def complete_reads(acquisition_plan: AcquisitionPlan, session: Session):
    for read in acquisition_plan.reads:
        read.status = ProcessStatus.COMPLETED
        session.add(read)
    session.commit()
    session.refresh(acquisition_plan)
    create_random_artifact_collection(
        session=session,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ACQUISITION_STORE,
        acquisition=acquisition_plan.acquisition,
    )


def create_random_instrument_type(
    *, session: Session, name: str | None = None
) -> InstrumentType:
    name = name or random_lower_string()
    instrument_type_create = InstrumentTypeCreate(name=name)
    return create_instrument_type(
        session=session, instrument_type_create=instrument_type_create
    )


def create_random_instrument(
    *, session: Session, instrument_type_id: int | None = None
) -> Instrument:
    if instrument_type_id is None:
        instrument_type_id = create_random_instrument_type(session=session).id
    instrument_create = InstrumentCreate(
        name=random_lower_string(), instrument_type_id=instrument_type_id
    )
    return create_instrument(session=session, instrument_create=instrument_create)
