from unittest.mock import patch

from sqlmodel import Session

from app.labware.crud import update_wellplate
from app.labware.events import handle_wellplate_location_update
from app.labware.models import Location, WellplateUpdate
from tests.labware.events import create_random_wellplate


def test_handle_wellplate_location_update(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)
    before = wellplate.location
    assert before == Location.EXTERNAL
    wellplate_in = WellplateUpdate(location=Location.CYTOMAT2)
    update_wellplate(session=db, db_wellplate=wellplate, wellplate_in=wellplate_in)

    with patch("app.labware.events.check_to_implement_plans") as mock_emit_event:
        handle_wellplate_location_update(
            wellplate_id=wellplate.id, origin=before, dest=Location.CYTOMAT2
        )
        mock_emit_event.assert_called_once_with(wellplate_id=wellplate.id)


def test_handle_wellplate_location_update_no_difference(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)
    assert wellplate.location == Location.EXTERNAL

    with patch("app.labware.events.check_to_implement_plans") as mock_emit_event:
        handle_wellplate_location_update(
            wellplate_id=wellplate.id, origin=Location.EXTERNAL, dest=Location.EXTERNAL
        )
        mock_emit_event.assert_not_called()
