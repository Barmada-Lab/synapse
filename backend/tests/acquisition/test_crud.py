from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.acquisition import crud
from app.acquisition.crud import create_acquisition_plan, update_plateread
from app.acquisition.flows.acquisition_planning import implement_plan
from app.acquisition.models import (
    AcquisitionCreate,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    AnalysisTrigger,
    ArtifactCollectionCreate,
    ArtifactType,
    ImagingPriority,
    InstrumentCreate,
    InstrumentTypeCreate,
    PlatereadSpecUpdate,
    ProcessStatus,
    Repository,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecCreate,
)
from app.labware.models import Location, Wellplate
from tests.acquisition.utils import (
    complete_reads,
    create_random_acquisition,
    create_random_acquisition_plan,
    create_random_analysis_spec,
    create_random_artifact_collection,
    create_random_instrument,
    create_random_instrument_type,
)
from tests.labware.events import create_random_wellplate
from tests.utils import random_lower_string


def test_create_acquisition(db: Session) -> None:
    name = random_lower_string()
    instrument = create_random_instrument(session=db)
    acquisition_create = AcquisitionCreate(name=name, instrument_id=instrument.id)

    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )
    assert acquisition.name == name


def test_create_acquisition_already_exists(db: Session) -> None:
    name = random_lower_string()
    instrument = create_random_instrument(session=db)
    acquisition_create = AcquisitionCreate(name=name, instrument_id=instrument.id)

    _ = crud.create_acquisition(session=db, acquisition_create=acquisition_create)
    with pytest.raises(IntegrityError):
        crud.create_acquisition(session=db, acquisition_create=acquisition_create)
    db.rollback()


def test_get_acquisition_by_name(db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    stored_acquisition = crud.get_acquisition_by_name(session=db, name=acquisition.name)
    assert stored_acquisition is not None
    assert acquisition.name == stored_acquisition.name


def test_get_acquisition_by_name_not_found(db: Session) -> None:
    name = random_lower_string()
    stored_acquisition = crud.get_acquisition_by_name(session=db, name=name)
    assert stored_acquisition is None


def test_create_artifact_collection(db: Session) -> None:
    instrument = create_random_instrument(session=db)
    acquisition_create = AcquisitionCreate(
        name=random_lower_string(), instrument_id=instrument.id
    )
    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )

    acquisition_id = acquisition.id
    location = Repository.ACQUISITION_STORE
    artifact_type = ArtifactType.ACQUISITION_DATA
    artifact_collection_create = ArtifactCollectionCreate(
        location=location,
        artifact_type=artifact_type,
        acquisition_id=acquisition_id,
    )

    artifact = crud.create_artifact_collection(
        session=db,
        artifact_collection_create=artifact_collection_create,
    )
    assert artifact.location == location
    assert artifact.artifact_type == artifact_type
    assert artifact.acquisition_id == acquisition_id

    db.refresh(acquisition)
    assert acquisition.collections_list[0].id == artifact.id


def test_create_artifact_collection_invalid_acquisition_id(db: Session) -> None:
    acquisition_id = 2**16
    artifact_collection_create = ArtifactCollectionCreate(
        location=Repository.ACQUISITION_STORE,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        acquisition_id=acquisition_id,
    )

    with pytest.raises(IntegrityError) as e:
        crud.create_artifact_collection(
            session=db,
            artifact_collection_create=artifact_collection_create,
        )
        assert "Acquisition not found" in str(e)
    db.rollback()


def test_create_artifact_duplicate_type_and_location(db: Session) -> None:
    """Each combination of ArtifactType and Repository should be unique"""
    acquisition = create_random_acquisition(session=db)

    acquisition_id = acquisition.id
    location = Repository.ACQUISITION_STORE
    artifact_type = ArtifactType.ACQUISITION_DATA
    artifact_collection_create = ArtifactCollectionCreate(
        location=location,
        artifact_type=artifact_type,
        acquisition_id=acquisition_id,
    )

    _ = crud.create_artifact_collection(
        session=db,
        artifact_collection_create=artifact_collection_create,
    )
    with pytest.raises(IntegrityError):
        crud.create_artifact_collection(
            session=db,
            artifact_collection_create=artifact_collection_create,
        )
    db.rollback()


def test_get_artifact_collection_by_key(db: Session) -> None:
    collection = create_random_artifact_collection(session=db)
    retrieved = crud.get_artifact_collection_by_key(
        session=db,
        acquisition_id=collection.acquisition_id,
        key=(collection.location, collection.artifact_type),
    )
    assert retrieved == collection


def test_create_acquisition_plan(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)

    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    interval = timedelta(minutes=1)
    priority = ImagingPriority.NORMAL

    name = random_lower_string()
    acquisition = create_random_acquisition(session=db, name=name)

    plan_create = AcquisitionPlanCreate(
        acquisition_id=acquisition.id,
        wellplate_id=wellplate_id,
        storage_location=storage_location,
        protocol_name=protocol_name,
        n_reads=n_reads,
        interval=interval,
        priority=priority,
    )

    record = create_acquisition_plan(session=db, plan_create=plan_create)

    assert record.wellplate_id == wellplate_id
    assert record.storage_location == storage_location
    assert record.protocol_name == protocol_name
    assert record.n_reads == n_reads
    assert record.interval == interval
    assert record.priority == priority
    assert record.reads == []


def test_acquisition_plan_with_no_reads_is_not_scheduled(db: Session) -> None:
    plan = create_random_acquisition_plan(session=db, n_reads=1)
    assert plan.reads == []
    assert plan.scheduled is False


def test_acquisition_plan_with_pending_reads_is_not_scheduled(db: Session) -> None:
    plan = create_random_acquisition_plan(session=db, n_reads=1)
    implement_plan(session=db, plan=plan)
    assert plan.reads[0].status == ProcessStatus.PENDING
    assert plan.scheduled is False


def test_acquisition_plan_with_scheduled_reads_is_scheduled(db: Session) -> None:
    plan = create_random_acquisition_plan(session=db, n_reads=1)
    implement_plan(session=db, plan=plan)
    plateread = plan.reads[0]
    plateread_in = PlatereadSpecUpdate(status=ProcessStatus.SCHEDULED)
    update_plateread(session=db, db_plateread=plateread, plateread_in=plateread_in)
    assert plan.reads[0].status == ProcessStatus.SCHEDULED
    assert plan.scheduled


def test_acquisition_plan_with_all_endstate_reads_is_not_scheduled(db: Session) -> None:
    plan = create_random_acquisition_plan(session=db, n_reads=1)
    implement_plan(session=db, plan=plan)
    complete_reads(session=db, acquisition_plan=plan)
    assert plan.completed
    assert plan.scheduled is False


def test_acquisition_plan_with_all_endstate_reads_is_completed(db: Session) -> None:
    endstates = list(filter(lambda s: s.is_endstate, ProcessStatus))
    plan = create_random_acquisition_plan(session=db, n_reads=len(endstates))
    implement_plan(session=db, plan=plan)
    for read, state in zip(plan.reads, endstates, strict=True):
        update_plateread(
            session=db,
            db_plateread=read,
            plateread_in=PlatereadSpecUpdate(status=state),
        )
    assert plan.completed


def test_acquisition_plan_unimplemented_is_not_completed(db: Session) -> None:
    plan = create_random_acquisition_plan(session=db, n_reads=1)
    assert not plan.completed


def test_acquisition_plan_with_not_all_endstate_reads_is_not_completed(
    db: Session,
) -> None:
    plan = create_random_acquisition_plan(session=db, n_reads=2)
    implement_plan(session=db, plan=plan)
    complete_reads(session=db, acquisition_plan=plan)
    update_plateread(
        session=db,
        db_plateread=plan.reads[0],
        plateread_in=PlatereadSpecUpdate(status=ProcessStatus.RUNNING),
    )
    assert not plan.completed


def test_create_acquisition_plan_with_long_name_fails(db: Session) -> None:
    name = "A" * 256
    with pytest.raises(ValidationError):
        create_random_acquisition_plan(session=db, name=name)


def test_create_acquisition_plan_with_long_protocol_name_fails(db: Session) -> None:
    protocol_name = "A" * 256
    with pytest.raises(ValidationError):
        create_random_acquisition_plan(session=db, protocol_name=protocol_name)


def test_create_acquisition_plan_with_zero_reads_fails(db: Session) -> None:
    with pytest.raises(ValidationError):
        create_random_acquisition_plan(session=db, n_reads=0)


def test_create_acquisition_plan_with_negative_reads_fails(db: Session) -> None:
    with pytest.raises(ValidationError):
        create_random_acquisition_plan(session=db, n_reads=-1)


def test_create_acquisition_plan_default_interval_is_zero(db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    wellplate = create_random_wellplate(session=db)
    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    priority = ImagingPriority.NORMAL

    plan_create = AcquisitionPlanCreate(
        wellplate_id=wellplate_id,
        acquisition_id=acquisition.id,
        storage_location=storage_location,
        protocol_name=protocol_name,
        n_reads=n_reads,
        # interval=interval, omit
        priority=priority,
    )

    assert plan_create.interval == timedelta(days=0)


def test_create_acquisition_plan_default_deadline_delta_is_none(db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    wellplate = create_random_wellplate(session=db)

    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    interval = timedelta(minutes=1)
    priority = ImagingPriority.NORMAL

    plan_create = AcquisitionPlanCreate(
        wellplate_id=wellplate_id,
        acquisition_id=acquisition.id,
        storage_location=storage_location,
        protocol_name=protocol_name,
        n_reads=n_reads,
        interval=interval,
        # deadline_delta=deadline_delta, omit
        priority=priority,
    )

    assert plan_create.deadline_delta is None


def test_create_acquisition_plan_default_priority_is_normal(db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    wellplate = create_random_wellplate(session=db)

    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    interval = timedelta(minutes=1)

    plan_create = AcquisitionPlanCreate(
        wellplate_id=wellplate_id,
        acquisition_id=acquisition.id,
        storage_location=storage_location,
        protocol_name=protocol_name,
        n_reads=n_reads,
        interval=interval,
        # priority=priority, omit
    )

    assert plan_create.priority == ImagingPriority.NORMAL


def test_create_acquisition_plan_with_duplicate_fk_raises_integrityerror(
    db: Session,
):
    plan_a = create_random_acquisition_plan(session=db)
    dump = plan_a.model_dump()
    with pytest.raises(IntegrityError):
        plan_create = AcquisitionPlanCreate.model_validate(dump)
        crud.create_acquisition_plan(session=db, plan_create=plan_create)
    db.rollback()  # reset session state

    # isolate name as the cause
    dump["name"] = random_lower_string()
    create_random_acquisition_plan(session=db, **dump)


def test_create_acquisition_plan_with_invalid_wellplate_id_raises_value_error(
    db: Session,
) -> None:
    assert db.get(Wellplate, 2**16) is None  # no such wellplate
    with pytest.raises(IntegrityError):
        create_random_acquisition_plan(session=db, wellplate_id=2**16)
    db.rollback()


def test_delete_wellplate_associated_with_acquisition_plan_cascades_delete(
    db: Session,
) -> None:
    wellplate = create_random_wellplate(session=db)
    plan = create_random_acquisition_plan(session=db, wellplate_id=wellplate.id)
    db.delete(wellplate)
    db.commit()
    assert db.get(AcquisitionPlan, plan.id) is None


def test_create_analysis_plan(db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    assert acquisition.id
    plan = crud.create_analysis_plan(session=db, acquisition_id=acquisition.id)
    assert plan.acquisition_id == acquisition.id


def test_create_duplicate_analysis_plan_raises_integrityerror(db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    assert acquisition.id
    _ = crud.create_analysis_plan(session=db, acquisition_id=acquisition.id)
    with pytest.raises(IntegrityError):
        crud.create_analysis_plan(session=db, acquisition_id=acquisition.id)
    db.rollback()


def test_create_analysis_spec(db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    assert acquisition.id
    plan = crud.create_analysis_plan(session=db, acquisition_id=acquisition.id)
    assert plan.id
    spec_create = SBatchAnalysisSpecCreate(
        trigger=AnalysisTrigger.END_OF_RUN,
        analysis_cmd="echo",
        analysis_args=["hello"],
        analysis_plan_id=plan.id,
    )
    spec = crud.create_analysis_spec(session=db, create=spec_create)
    assert spec.analysis_plan_id == plan.id
    assert not any(spec.jobs)


def test_delete_analysis_spec(db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    assert acquisition.id
    plan = crud.create_analysis_plan(session=db, acquisition_id=acquisition.id)
    assert plan.id
    spec_create = SBatchAnalysisSpecCreate(
        trigger=AnalysisTrigger.END_OF_RUN,
        analysis_cmd="echo",
        analysis_args=["hello"],
        analysis_plan_id=plan.id,
    )
    spec = crud.create_analysis_spec(session=db, create=spec_create)
    db.delete(spec)


def test_delete_analysis_plan_cascades_delete(db: Session) -> None:
    spec = create_random_analysis_spec(session=db)
    db.delete(spec.analysis_plan)
    db.commit()
    assert db.get(SBatchAnalysisSpec, spec.id) is None


def test_create_instrument_type(db: Session) -> None:
    name = random_lower_string()
    instrument_type_create = InstrumentTypeCreate(name=name)
    instrument_type = crud.create_instrument_type(
        session=db, instrument_type_create=instrument_type_create
    )
    assert instrument_type.name == name


def test_get_instrument_type_by_name(db: Session) -> None:
    name = random_lower_string()
    instrument_type_create = InstrumentTypeCreate(name=name)
    instrument_type = crud.create_instrument_type(
        session=db, instrument_type_create=instrument_type_create
    )
    assert crud.get_instrument_type_by_name(session=db, name=name) == instrument_type


def test_create_instrument_type_already_exists(db: Session) -> None:
    name = random_lower_string()
    instrument_type_create = InstrumentTypeCreate(name=name)
    _ = crud.create_instrument_type(
        session=db, instrument_type_create=instrument_type_create
    )
    with pytest.raises(IntegrityError):
        crud.create_instrument_type(
            session=db, instrument_type_create=instrument_type_create
        )
    db.rollback()


def test_create_instrument(db: Session) -> None:
    instrument_type = create_random_instrument_type(session=db)
    name = random_lower_string()
    instrument_create = InstrumentCreate(
        name=name, instrument_type_id=instrument_type.id
    )
    instrument = crud.create_instrument(session=db, instrument_create=instrument_create)
    assert instrument.name == name
    assert instrument.instrument_type_id == instrument_type.id


def test_get_instrument_by_name(db: Session) -> None:
    instrument_type = create_random_instrument_type(session=db)
    name = random_lower_string()
    instrument_create = InstrumentCreate(
        name=name, instrument_type_id=instrument_type.id
    )
    instrument = crud.create_instrument(session=db, instrument_create=instrument_create)
    assert crud.get_instrument_by_name(session=db, name=name) == instrument


def test_create_duplicate_instrument_raises_integrityerror(db: Session) -> None:
    instrument_type = create_random_instrument_type(session=db)
    name = random_lower_string()
    instrument_create = InstrumentCreate(
        name=name, instrument_type_id=instrument_type.id
    )
    _ = crud.create_instrument(session=db, instrument_create=instrument_create)
    with pytest.raises(IntegrityError):
        crud.create_instrument(session=db, instrument_create=instrument_create)
    db.rollback()
