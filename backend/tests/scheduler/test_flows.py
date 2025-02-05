from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlmodel import Session

from app.acquisition import crud
from app.acquisition.models import (
    ImagingPriority,
    PlatereadSpecUpdate,
    ProcessStatus,
)
from app.labware import crud as labware_crud
from app.labware.models import Location, WellplateUpdate
from app.scheduler.flows import (
    any_platereads_running,
    cancel_past_deadline,
    get_next_task,
    schedule,
)
from tests.acquisition.utils import (
    create_random_acquisition_plan,
    create_random_wellplate,
)


def test_cancel_past_deadline(db: Session):
    """cancel_past_deadline should cancel platereads that are past their deadline"""
    plan = create_random_acquisition_plan(
        session=db,
        deadline_delta=timedelta(hours=-1),
    )
    crud.implement_plan(session=db, plan=plan)
    cancel_past_deadline(db)
    assert plan.reads[0].status == ProcessStatus.CANCELLED


def test_cancel_past_deadline_none(db: Session):
    """cancel_past_deadline should not cancel platereads that are not past their deadline"""
    plan = create_random_acquisition_plan(
        session=db,
        deadline_delta=timedelta(minutes=1),
    )
    crud.implement_plan(session=db, plan=plan)
    cancel_past_deadline(db)
    assert plan.reads[0].status == ProcessStatus.PENDING


def test_any_platereads_running_false(db: Session):
    """any_platereads_running should return false if there are no running platereads"""
    plan = create_random_acquisition_plan(session=db)
    crud.implement_plan(session=db, plan=plan)
    assert any_platereads_running(db) is False


def test_any_platereads_running_true(db: Session):
    """any_platereads_running should return true if there are running platereads"""
    plan = create_random_acquisition_plan(session=db)
    crud.implement_plan(session=db, plan=plan)
    plateread = plan.reads[0]
    crud.update_plateread(
        session=db,
        db_plateread=plateread,
        plateread_in=PlatereadSpecUpdate(status=ProcessStatus.RUNNING),
    )
    assert any_platereads_running(db) is True


def test_get_next_task(db: Session):
    """
    get_next_task should return the next plateread spec matching the provided imaging priority
    with a start_after time less than the current time
    """
    wellplate = create_random_wellplate(session=db)
    labware_crud.update_wellplate(
        session=db,
        db_wellplate=wellplate,
        wellplate_in=WellplateUpdate(location=Location.CYTOMAT2),
    )
    plan = create_random_acquisition_plan(
        session=db,
        priority=ImagingPriority.NORMAL,
        wellplate_id=wellplate.id,
        storage_location=Location.CYTOMAT2,
    )
    crud.implement_plan(session=db, plan=plan)
    plateread = plan.reads[0]
    assert (
        get_next_task(db, datetime.now(timezone.utc), ImagingPriority.NORMAL)
        == plateread
    )
    assert plateread.acquisition_plan.wellplate.location == plan.storage_location


def test_get_next_task_start_after_in_future(db: Session):
    """get_next_task should return None if there are no plateread specs with a start_after time in the future"""
    wellplate = create_random_wellplate(session=db)
    labware_crud.update_wellplate(
        session=db,
        db_wellplate=wellplate,
        wellplate_in=WellplateUpdate(location=Location.CYTOMAT2),
    )
    plan = create_random_acquisition_plan(
        session=db,
        priority=ImagingPriority.NORMAL,
        wellplate_id=wellplate.id,
        storage_location=Location.CYTOMAT2,
    )
    crud.implement_plan(session=db, plan=plan)
    assert (
        get_next_task(
            db, datetime.now(timezone.utc) + timedelta(hours=-1), ImagingPriority.NORMAL
        )
        is None
    )


def test_get_next_task_no_matching_prio(db: Session):
    """get_next_task should return None if there are no plateread specs with a matching priority"""
    wellplate = create_random_wellplate(session=db)
    labware_crud.update_wellplate(
        session=db,
        db_wellplate=wellplate,
        wellplate_in=WellplateUpdate(location=Location.CYTOMAT2),
    )
    plan = create_random_acquisition_plan(
        session=db,
        priority=ImagingPriority.LOW,
        wellplate_id=wellplate.id,
        storage_location=Location.CYTOMAT2,
    )
    crud.implement_plan(session=db, plan=plan)
    assert get_next_task(db, datetime.now(timezone.utc), ImagingPriority.NORMAL) is None


def test_get_next_task_no_pending(db: Session):
    """get_next_task should return None if there are no pending plateread specs"""
    wellplate = create_random_wellplate(session=db)
    labware_crud.update_wellplate(
        session=db,
        db_wellplate=wellplate,
        wellplate_in=WellplateUpdate(location=Location.CYTOMAT2),
    )
    plan = create_random_acquisition_plan(
        session=db,
        priority=ImagingPriority.NORMAL,
        wellplate_id=wellplate.id,
        storage_location=Location.CYTOMAT2,
    )
    crud.implement_plan(session=db, plan=plan)
    plateread = plan.reads[0]
    crud.update_plateread(
        session=db,
        db_plateread=plateread,
        plateread_in=PlatereadSpecUpdate(status=ProcessStatus.RUNNING),
    )
    db.refresh(plateread)
    assert plateread.status == ProcessStatus.RUNNING
    assert get_next_task(db, datetime.now(timezone.utc), ImagingPriority.NORMAL) is None


def test_get_next_task_no_matching_location(db: Session):
    """get_next_task should return None if there are no pending plateread specs with a matching location"""
    wellplate = create_random_wellplate(session=db)
    assert wellplate.location == Location.EXTERNAL
    plan = create_random_acquisition_plan(
        session=db,
        priority=ImagingPriority.NORMAL,
        wellplate_id=wellplate.id,
        storage_location=Location.CYTOMAT2,
    )
    crud.implement_plan(session=db, plan=plan)
    assert get_next_task(db, datetime.now(timezone.utc), ImagingPriority.NORMAL) is None


def test_schedule_cancels_past_deadline():
    """
    Schedule should begin by cancelling platereads that are past their deadline
    """
    with patch("app.scheduler.flows.cancel_past_deadline") as cancel_mock:
        schedule()
        cancel_mock.assert_called_once()


def test_schedule_doesnt_check_for_normal_prio_if_any_platereads_running():
    """
    Schedule should return without attempting to schedule any platereads if there are
    platereads running
    """
    with (
        patch("app.scheduler.flows.any_platereads_running", return_value=True),
        patch(
            "app.scheduler.flows.get_next_normal_prio", return_value=None
        ) as get_next_normal_prio_mock,
    ):
        schedule()
        get_next_normal_prio_mock.assert_not_called()


def test_schedule_submits_normal_prio_if_possible(db: Session):
    """
    Schedule will submit a normal priority plateread if there are no low priority platereads pending
    """
    normal_plan = create_random_acquisition_plan(
        session=db, priority=ImagingPriority.NORMAL
    )
    crud.implement_plan(session=db, plan=normal_plan)
    plateread = normal_plan.reads[0]
    with (
        patch(
            "app.scheduler.flows.get_next_normal_prio", return_value=plateread
        ) as get_next_normal_prio_mock,
        patch(
            "app.scheduler.flows.get_future_normal_prio"
        ) as get_future_normal_prio_mock,
        patch("app.scheduler.flows.get_next_low_prio") as get_next_low_prio_mock,
        patch("app.scheduler.flows.submit_plateread_spec") as submit_mock,
    ):
        schedule()
        get_next_normal_prio_mock.assert_called_once()
        get_future_normal_prio_mock.assert_not_called()
        get_next_low_prio_mock.assert_not_called()
        submit_mock.assert_called_once()


def test_schedule_submits_low_prio_if_no_future_normal_prio(db: Session):
    """
    Schedule will check for low priority platereads if there are no normal priority platereads pending
    """
    low_plan = create_random_acquisition_plan(session=db, priority=ImagingPriority.LOW)
    crud.implement_plan(session=db, plan=low_plan)
    plateread = low_plan.reads[0]
    with (
        patch(
            "app.scheduler.flows.get_next_normal_prio", return_value=None
        ) as get_next_normal_prio_mock,
        patch(
            "app.scheduler.flows.get_future_normal_prio", return_value=None
        ) as get_future_normal_prio_mock,
        patch(
            "app.scheduler.flows.get_next_low_prio", return_value=plateread
        ) as get_next_low_prio_mock,
        patch("app.scheduler.flows.submit_plateread_spec") as submit_mock,
    ):
        schedule()
        get_next_normal_prio_mock.assert_called_once()
        get_future_normal_prio_mock.assert_called_once()
        get_next_low_prio_mock.assert_called_once()
        submit_mock.assert_called_once()


def test_schedule_doesnt_submit_low_prio_if_next_normal_prio_is_too_soon(db: Session):
    """
    Schedule should not check to submit a low priority plateread if the next normal priority plateread's start_after
    time is too soon
    """
    normal_plan = create_random_acquisition_plan(
        session=db, priority=ImagingPriority.NORMAL
    )
    crud.implement_plan(session=db, plan=normal_plan)
    normal_plateread = normal_plan.reads[0]
    normal_plateread.start_after = datetime.now(timezone.utc) + timedelta(hours=5)
    db.add(normal_plateread)
    db.commit()

    low_plan = create_random_acquisition_plan(session=db, priority=ImagingPriority.LOW)
    crud.implement_plan(session=db, plan=low_plan)
    low_plateread = low_plan.reads[0]
    with (
        patch(
            "app.scheduler.flows.get_future_normal_prio", return_value=normal_plateread
        ) as get_future_normal_prio_mock,
        patch(
            "app.scheduler.flows.get_next_low_prio", return_value=low_plateread
        ) as get_next_low_prio_mock,
        patch("app.scheduler.flows.submit_plateread_spec") as submit_mock,
    ):
        schedule()
        get_future_normal_prio_mock.assert_called_once()
        get_next_low_prio_mock.assert_not_called()
        submit_mock.assert_not_called()
