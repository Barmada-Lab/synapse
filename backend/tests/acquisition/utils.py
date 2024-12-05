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
    Repository,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecCreate,
)
from app.labware.models import Location
from tests.labware.events import create_random_wellplate
from tests.utils import random_lower_string


def create_random_acquisition(*, session: Session, **kwargs) -> Acquisition:
    kwargs.setdefault("name", random_lower_string())
    acquisition_create = AcquisitionCreate(name=kwargs["name"])
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
    *, session: Session, acquisition: Acquisition | None = None
) -> SBatchAnalysisSpec:
    analysis_plan = create_random_analysis_plan(
        session=session, acquisition=acquisition
    )
    analysis_create = SBatchAnalysisSpecCreate(
        trigger=random.choice(list(AnalysisTrigger)),
        analysis_cmd=random_lower_string(),
        analysis_args=[random_lower_string()],
        analysis_plan_id=analysis_plan.id,
    )
    return create_analysis_spec(
        session=session,
        create=analysis_create,
    )


def create_random_acquisition_plan(
    *, session: Session, wellplate_id: int | None = None, **kwargs
) -> AcquisitionPlan:
    kwargs.setdefault("name", random_lower_string())
    acquisition_create = AcquisitionCreate(name=kwargs["name"])
    acquisition = create_acquisition(
        session=session, acquisition_create=acquisition_create
    )

    if wellplate_id is None:
        wellplate = create_random_wellplate(session=session)
        wellplate_id = int(wellplate.id)

    kwargs.setdefault("wellplate_id", wellplate_id)
    kwargs.setdefault("storage_location", Location.CQ1)
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
    artifact_type: ArtifactType = ArtifactType.ACQUISITION,
    location: Repository = Repository.ACQUISITION,
) -> ArtifactCollection:
    acquisition_create = AcquisitionCreate(name=random_lower_string())
    acquisition = create_acquisition(
        session=session, acquisition_create=acquisition_create
    )
    artifact_collection_create = ArtifactCollectionCreate(
        acquisition_id=acquisition.id, artifact_type=artifact_type, location=location
    )
    collection = create_artifact_collection(
        session=session,
        acquisition_id=acquisition.id,  # type: ignore
        artifact_collection_create=artifact_collection_create,
    )
    collection.path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=collection.path, delete=False) as f:
        f.write(os.urandom(1024))
    return collection
