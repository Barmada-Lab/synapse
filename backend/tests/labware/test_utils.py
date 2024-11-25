from unittest.mock import patch

from sqlmodel import Session

from app.labware.crud import update_wellplate
from app.labware.events import emit_wellplate_location_update
from app.labware.models import Location, WellplateUpdate
from tests.labware.events import create_random_wellplate


def test_emit_wellplate_location_update(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)
    before = wellplate.location
    assert before == Location.EXTERNAL
    wellplate_in = WellplateUpdate(location=Location.CYTOMAT2)
    updated_wellplate = update_wellplate(
        session=db, db_wellplate=wellplate, wellplate_in=wellplate_in
    )

    with patch("app.labware.events.emit_event") as mock_emit_event:
        emit_wellplate_location_update(wellplate=updated_wellplate, before=before)
        mock_emit_event.assert_called_once_with(
            "wellplate.location_update",
            resource={
                "prefect.resource.id": f"wellplate.{updated_wellplate.name}",
                "location.before": Location.EXTERNAL.value,
                "location.after": Location.CYTOMAT2.value,
            },
        )


def test_emit_wellplate_location_update_no_difference(db: Session) -> None:
    wellplate = create_random_wellplate(session=db)
    assert wellplate.location == Location.EXTERNAL

    with patch("app.labware.events.emit_event") as mock_emit_event:
        emit_wellplate_location_update(wellplate=wellplate, before=Location.EXTERNAL)
        mock_emit_event.assert_not_called()
