from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.labware.models import Location, Wellplate
from app.procedures.crud import (
    create_acquisition_plan,
    get_acquisition_plan_by_name,
    schedule_plan,
)
from app.procedures.models import (
    AcquisitionPlanCreate,
    ImagingPriority,
    PlateReadStatus,
)
from tests.labware.utils import create_random_wellplate
from tests.procedures.utils import create_random_acquisition_plan
from tests.utils import random_lower_string


def test_create_acquisition_plan(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)

    name = random_lower_string()
    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    interval = timedelta(minutes=1)
    priority = ImagingPriority.NORMAL

    plan_create = AcquisitionPlanCreate(
        name=name,
        wellplate_id=wellplate_id,
        storage_location=storage_location,
        protocol_name=protocol_name,
        n_reads=n_reads,
        interval=interval,
        priority=priority,
    )

    record = create_acquisition_plan(session=db, plan_create=plan_create)

    assert record.name == name
    assert record.wellplate_id == wellplate_id
    assert record.storage_location == storage_location
    assert record.protocol_name == protocol_name
    assert record.n_reads == n_reads
    assert record.interval == interval
    assert record.priority == priority
    assert record.scheduled_reads == []


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
    wellplate = create_random_wellplate(session=db)

    name = random_lower_string()
    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    priority = ImagingPriority.NORMAL

    plan_create = AcquisitionPlanCreate(
        name=name,
        wellplate_id=wellplate_id,
        storage_location=storage_location,
        protocol_name=protocol_name,
        n_reads=n_reads,
        # interval=interval, omit
        priority=priority,
    )

    assert plan_create.interval == timedelta(days=0)


def test_create_acquisition_plan_default_deadline_delta_is_zero(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)

    name = random_lower_string()
    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    interval = timedelta(minutes=1)
    priority = ImagingPriority.NORMAL

    plan_create = AcquisitionPlanCreate(
        name=name,
        wellplate_id=wellplate_id,
        storage_location=storage_location,
        protocol_name=protocol_name,
        n_reads=n_reads,
        interval=interval,
        # deadline_delta=deadline_delta, omit
        priority=priority,
    )

    assert plan_create.deadline_delta == timedelta(days=0)


def test_create_acquisition_plan_default_priority_is_normal(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)

    name = random_lower_string()
    wellplate_id = wellplate.id
    storage_location = Location.CQ1
    protocol_name = random_lower_string()
    n_reads = 1
    interval = timedelta(minutes=1)

    plan_create = AcquisitionPlanCreate(
        name=name,
        wellplate_id=wellplate_id,
        storage_location=storage_location,
        protocol_name=protocol_name,
        n_reads=n_reads,
        interval=interval,
        # priority=priority, omit
    )

    assert plan_create.priority == ImagingPriority.NORMAL


def test_create_acquisition_plan_with_duplicate_name_raises_integrityerror(
    db: Session,
):
    plan_a = create_random_acquisition_plan(session=db)
    dump = plan_a.model_dump()
    with pytest.raises(IntegrityError):
        create_random_acquisition_plan(session=db, **dump)
    db.rollback()  # reset session state

    # isolate name as the cause
    dump["name"] = random_lower_string()
    create_random_acquisition_plan(session=db, **dump)


def test_create_acquisition_plan_with_invalid_wellplate_id_raises_value_error(
    db: Session,
) -> None:
    assert db.get(Wellplate, 2**16) is None  # no such wellplate
    with pytest.raises(ValueError):
        create_random_acquisition_plan(session=db, wellplate_id=2**16)


def test_delete_wellplate_associated_with_acquisition_plan_raises_integrityerror(
    db: Session,
) -> None:
    wellplate = create_random_wellplate(session=db)
    _ = create_random_acquisition_plan(session=db, wellplate_id=wellplate.id)
    with pytest.raises(IntegrityError):
        db.delete(wellplate)
        db.commit()
    db.rollback()  # reset session state


def test_get_acquisition_plan_by_name(db: Session) -> None:
    plan_a = create_random_acquisition_plan(session=db)
    plan_b = get_acquisition_plan_by_name(session=db, name=plan_a.name)
    assert plan_b == plan_a


def test_get_acquisition_plan_by_name_not_found(db: Session) -> None:
    plan = get_acquisition_plan_by_name(session=db, name=random_lower_string())
    assert plan is None


def test_materialize_schedule(db: Session) -> None:
    plan = create_random_acquisition_plan(
        session=db,
        n_reads=2,
        interval=timedelta(minutes=2),
        deadline_delta=timedelta(minutes=1),
    )
    plan = schedule_plan(session=db, plan=plan)
    assert len(plan.scheduled_reads) == 2
    assert all(r.status == PlateReadStatus.PENDING for r in plan.scheduled_reads)

    t0 = plan.scheduled_reads[0]
    t1 = plan.scheduled_reads[1]
    assert t0.start_after + timedelta(minutes=2) == t1.start_after
    assert t0.start_after + timedelta(minutes=1) == t0.deadline
