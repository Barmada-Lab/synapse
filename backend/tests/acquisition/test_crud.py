from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.acquisition import crud
from app.acquisition.crud import (
    create_acquisition_plan,
    schedule_plan,
)
from app.acquisition.models import (
    AcquisitionCreate,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    Artifact,
    ArtifactCollectionCreate,
    ArtifactCreate,
    ArtifactType,
    ImagingPriority,
    PlatereadSpecUpdate,
    ProcessStatus,
    Repository,
)
from app.labware.models import Location, Wellplate
from tests.acquisition.utils import (
    create_random_acquisition,
    create_random_acquisition_plan,
    create_random_artifact_collection,
)
from tests.labware.events import create_random_wellplate
from tests.utils import random_lower_string


def test_create_acquisition_plan(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)

    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    interval = timedelta(minutes=1)
    priority = ImagingPriority.NORMAL

    name = random_lower_string()
    acquisition_create = AcquisitionCreate(name=name)
    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )

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
    assert record.schedule == []


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


def test_create_acquisition_plan_default_deadline_delta_is_zero(db: Session) -> None:
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

    assert plan_create.deadline_delta == timedelta(days=0)


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


def test_materialize_schedule(db: Session) -> None:
    plan = create_random_acquisition_plan(
        session=db,
        n_reads=2,
        interval=timedelta(minutes=2),
        deadline_delta=timedelta(minutes=1),
    )
    plan = schedule_plan(session=db, plan=plan)
    assert len(plan.schedule) == 2
    assert all(r.status == ProcessStatus.PENDING for r in plan.schedule)

    t0 = plan.schedule[0]
    t1 = plan.schedule[1]
    assert t0.start_after + timedelta(minutes=2) == t1.start_after
    assert t0.start_after + timedelta(minutes=1) == t0.deadline


def test_update_plateread(db: Session) -> None:
    plan = create_random_acquisition_plan(session=db)
    plan = schedule_plan(session=db, plan=plan)

    plateread = plan.schedule[0]
    plateread_in = PlatereadSpecUpdate(status=ProcessStatus.COMPLETED)
    updated = crud.update_plateread(
        session=db, db_plateread=plateread, plateread_in=plateread_in
    )
    assert updated.status == ProcessStatus.COMPLETED


def test_create_acquisition(db: Session) -> None:
    name = random_lower_string()
    acquisition_create = AcquisitionCreate(name=name)

    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )
    assert acquisition.name == name


def test_create_acquisition_already_exists(db: Session) -> None:
    name = random_lower_string()
    acquisition_create = AcquisitionCreate(name=name)

    _ = crud.create_acquisition(session=db, acquisition_create=acquisition_create)
    with pytest.raises(IntegrityError):
        crud.create_acquisition(session=db, acquisition_create=acquisition_create)
    db.rollback()


def test_get_acquisition_by_name(db: Session) -> None:
    name = random_lower_string()
    acquisition_create = AcquisitionCreate(name=name)

    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )
    stored_acquisition = crud.get_acquisition_by_name(session=db, name=name)
    assert stored_acquisition is not None
    assert acquisition.name == stored_acquisition.name


def test_get_acquisition_by_name_not_found(db: Session) -> None:
    name = random_lower_string()
    stored_acquisition = crud.get_acquisition_by_name(session=db, name=name)
    assert stored_acquisition is None


def test_create_artifact_collection(db: Session) -> None:
    acquisition_create = AcquisitionCreate(name=random_lower_string())
    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )

    acquisition_id = acquisition.id
    location = Repository.ACQUISITION
    artifact_type = ArtifactType.ACQUISITION
    artifact_collection_create = ArtifactCollectionCreate(
        location=location,
        artifact_type=artifact_type,
        acquisition_id=acquisition_id,
    )

    artifact = crud.create_artifact_collection(
        session=db,
        acquisition_id=acquisition_id,
        artifact_collection_create=artifact_collection_create,
    )
    assert artifact.location == location
    assert artifact.artifact_type == artifact_type
    assert artifact.acquisition_id == acquisition_id

    db.refresh(acquisition)
    assert acquisition.collections[0].id == artifact.id


def test_create_artifact_collection_invalid_acquisition_id(db: Session) -> None:
    acquisition_id = 2**16
    artifact_collection_create = ArtifactCollectionCreate(
        location=Repository.ACQUISITION,
        artifact_type=ArtifactType.ACQUISITION,
        acquisition_id=acquisition_id,
    )

    with pytest.raises(IntegrityError) as e:
        crud.create_artifact_collection(
            session=db,
            acquisition_id=acquisition_id,
            artifact_collection_create=artifact_collection_create,
        )
        assert "Acquisition not found" in str(e)
    db.rollback()


def test_create_artifact_duplicate_type_and_location(db: Session) -> None:
    """Each combination of ArtifactType and Repository should be unique"""
    acquisition_create = AcquisitionCreate(name=random_lower_string())
    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )

    acquisition_id = acquisition.id
    location = Repository.ACQUISITION
    artifact_type = ArtifactType.ACQUISITION
    artifact_collection_create = ArtifactCollectionCreate(
        location=location,
        artifact_type=artifact_type,
        acquisition_id=acquisition_id,
    )

    _ = crud.create_artifact_collection(
        session=db,
        acquisition_id=acquisition_id,  # type: ignore
        artifact_collection_create=artifact_collection_create,
    )
    with pytest.raises(IntegrityError):
        crud.create_artifact_collection(
            session=db,
            acquisition_id=acquisition_id,  # type: ignore
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


def test_create_artifact(db: Session) -> None:
    collection = create_random_artifact_collection(session=db)
    artifact_create = ArtifactCreate(
        name=random_lower_string(), collection_id=collection.id
    )
    assert collection.id
    crud.create_artifact(
        session=db,
        artifact_collection_id=collection.id,
        artifact_create=artifact_create,
    )


def test_delete_artifact_cascade_from_artifact_collection_delete(db: Session) -> None:
    collection = create_random_artifact_collection(session=db)
    artifact_create = ArtifactCreate(
        name=random_lower_string(), collection_id=collection.id
    )
    assert collection.id
    artifact = crud.create_artifact(
        session=db,
        artifact_collection_id=collection.id,
        artifact_create=artifact_create,
    )
    db.delete(collection)
    db.commit()
    assert db.get(Artifact, artifact.id) is None
