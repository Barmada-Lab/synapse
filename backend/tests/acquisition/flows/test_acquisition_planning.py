from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlmodel import Session

from app.acquisition import crud
from app.acquisition.flows.acquisition_planning import (
    check_to_implement_plans,
    implement_plan,
    schedule_reads,
)
from app.acquisition.models import PlatereadSpecUpdate, ProcessStatus
from app.labware import crud as labware_crud
from app.labware.models import Location, WellplateUpdate
from tests.acquisition.utils import (
    create_random_acquisition_plan,
)


def test_update_plateread(db: Session) -> None:
    plan = create_random_acquisition_plan(session=db)
    plan = implement_plan(session=db, plan=plan)

    plateread = plan.reads[0]
    plateread_in = PlatereadSpecUpdate(status=ProcessStatus.COMPLETED)
    updated = crud.update_plateread(
        session=db, db_plateread=plateread, plateread_in=plateread_in
    )
    assert updated.status == ProcessStatus.COMPLETED


def test_implement_plan(db: Session) -> None:
    plan = create_random_acquisition_plan(
        session=db,
        n_reads=2,
        interval=timedelta(minutes=2),
    )
    plan = implement_plan(session=db, plan=plan)
    assert len(plan.reads) == 2
    assert all(r.status == ProcessStatus.PENDING for r in plan.reads)

    t0 = plan.reads[0]
    t1 = plan.reads[1]
    assert t0.start_after + timedelta(minutes=2) == t1.start_after


def test_schedule_reads(db: Session) -> None:
    plan = create_random_acquisition_plan(
        session=db, storage_location=Location.CYTOMAT2, n_reads=2
    )
    implement_plan(session=db, plan=plan)
    with patch(
        "app.acquisition.flows.acquisition_planning.submit_plateread_spec"
    ) as mock_submit_plateread_spec:
        schedule_reads(session=db, plan=plan)
        assert mock_submit_plateread_spec.call_count == 2


def test_schedule_reads_not_pending(db: Session) -> None:
    """Reads that are not pending are not scheduled"""
    plan = create_random_acquisition_plan(
        session=db, storage_location=Location.CYTOMAT2, n_reads=2
    )
    plan = implement_plan(session=db, plan=plan)

    plateread = plan.reads[0]
    plateread_in = PlatereadSpecUpdate(status=ProcessStatus.SCHEDULED)
    crud.update_plateread(session=db, db_plateread=plateread, plateread_in=plateread_in)

    with patch(
        "app.acquisition.flows.acquisition_planning.submit_plateread_spec"
    ) as mock_submit_plateread_spec:
        schedule_reads(session=db, plan=plan)
        assert mock_submit_plateread_spec.call_count == 1


def test_check_to_implement_plans(db: Session) -> None:
    acquisition_plan = create_random_acquisition_plan(
        session=db, storage_location=Location.CYTOMAT2, n_reads=2
    )
    assert acquisition_plan.reads == []

    wellplate = acquisition_plan.wellplate
    assert wellplate.location == Location.EXTERNAL
    wellplate_in = WellplateUpdate(location=Location.CYTOMAT2)
    labware_crud.update_wellplate(
        session=db, db_wellplate=wellplate, wellplate_in=wellplate_in
    )

    with patch(
        "app.acquisition.flows.acquisition_planning.submit_plateread_spec"
    ) as mock_submit_plateread_spec:
        check_to_implement_plans(wellplate_id=wellplate.id)  # type: ignore[arg-type]
        assert mock_submit_plateread_spec.call_count == 2

    db.refresh(acquisition_plan)
    assert acquisition_plan.reads != []


def test_check_to_implement_plans_already_implemented(db: Session) -> None:
    acquisition_plan = create_random_acquisition_plan(
        session=db, storage_location=Location.CYTOMAT2, n_reads=2
    )
    assert acquisition_plan.reads == []

    wellplate = acquisition_plan.wellplate
    assert wellplate.location == Location.EXTERNAL
    wellplate_in = WellplateUpdate(location=Location.CYTOMAT2)
    labware_crud.update_wellplate(
        session=db, db_wellplate=wellplate, wellplate_in=wellplate_in
    )

    check_to_implement_plans(wellplate_id=wellplate.id)  # type: ignore[arg-type]
    db.refresh(acquisition_plan)
    assert acquisition_plan.reads != []

    with patch(
        "app.acquisition.flows.acquisition_planning.submit_plateread_spec"
    ) as mock_submit_plateread_spec:
        check_to_implement_plans(wellplate_id=wellplate.id)  # type: ignore[arg-type]
        # won't resubmit scheduled reads
        mock_submit_plateread_spec.assert_not_called()


def test_check_to_implement_plans_different_storage_location(db: Session) -> None:
    acquisition_plan = create_random_acquisition_plan(
        session=db, storage_location=Location.HOTEL
    )
    assert acquisition_plan.reads == []

    wellplate = acquisition_plan.wellplate
    assert wellplate.location == Location.EXTERNAL
    wellplate_in = WellplateUpdate(location=Location.CYTOMAT2)
    labware_crud.update_wellplate(
        session=db, db_wellplate=wellplate, wellplate_in=wellplate_in
    )

    with patch(
        "app.acquisition.flows.acquisition_planning.submit_plateread_spec"
    ) as mock_submit_plateread_spec:
        check_to_implement_plans(wellplate_id=wellplate.id)  # type: ignore[arg-type]
        mock_submit_plateread_spec.assert_not_called()

    db.refresh(acquisition_plan)
    # plate is not present in acquisition plan's storage_location, so scheduling
    # does not occur.
    assert acquisition_plan.reads == []


def test_check_to_schedule_acquisition_no_wellplate() -> None:
    with pytest.raises(ValueError):
        check_to_implement_plans(wellplate_id=2**16)
