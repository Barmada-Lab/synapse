from unittest.mock import patch

from sqlmodel import Session

from app.acquisition.crud import schedule_plan, update_plateread
from app.acquisition.events import emit_plateread_status_update
from app.acquisition.models import PlatereadSpecUpdate, ProcessStatus
from tests.acquisition.utils import create_random_acquisition_plan


def test_emit_plateread_status_update(db: Session):
    acquisition_plan = create_random_acquisition_plan(session=db)
    schedule_plan(session=db, plan=acquisition_plan)

    plateread = acquisition_plan.schedule[0]
    acquisition_name = acquisition_plan.acquisition.name
    assert plateread.status == ProcessStatus.PENDING
    plateread_in = PlatereadSpecUpdate(status=ProcessStatus.RUNNING)
    updated = update_plateread(
        session=db, db_plateread=plateread, plateread_in=plateread_in
    )
    resource_id = f"plateread.{plateread.id}"
    plateread_resource = {
        "prefect.resource.id": resource_id,
        "status.before": ProcessStatus.PENDING.value,
        "status.after": ProcessStatus.RUNNING.value,
    }
    related_resource = {
        "prefect.resource.id": f"acquisition.{acquisition_name}",
        "prefect.resource.role": "automation",
    }
    with patch("app.acquisition.events.emit_event") as emit_event_mock:
        emit_plateread_status_update(plateread=updated, before=ProcessStatus.PENDING)
        emit_event_mock.assert_called_once_with(
            "plateread.status_update",
            resource=plateread_resource,
            related=[related_resource],
        )


def test_emit_plateread_status_update_no_difference(db: Session):
    acquisition_plan = create_random_acquisition_plan(session=db)
    schedule_plan(session=db, plan=acquisition_plan)

    plateread = acquisition_plan.schedule[0]
    assert plateread.status == ProcessStatus.PENDING
    with patch("app.acquisition.events.emit_event") as emit_event_mock:
        emit_plateread_status_update(plateread=plateread, before=ProcessStatus.PENDING)
        emit_event_mock.assert_not_called()
