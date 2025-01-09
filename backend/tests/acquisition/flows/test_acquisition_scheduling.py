import pytest
from sqlmodel import Session

from app.acquisition.flows.acquisition_scheduling import check_to_schedule_acquisition
from app.labware import crud as labware_crud
from app.labware.models import Location, WellplateUpdate
from tests.acquisition.utils import (
    create_random_acquisition_plan,
)


def test_check_to_schedule_acquisition(db: Session) -> None:
    acquisition_plan = create_random_acquisition_plan(
        session=db, storage_location=Location.CYTOMAT2
    )
    assert acquisition_plan.schedule == []

    wellplate = acquisition_plan.wellplate
    assert wellplate.location == Location.EXTERNAL
    wellplate_in = WellplateUpdate(location=Location.CYTOMAT2)
    labware_crud.update_wellplate(
        session=db, db_wellplate=wellplate, wellplate_in=wellplate_in
    )

    resource_id = f"wellplate.{wellplate.name}"
    check_to_schedule_acquisition(resource_id=resource_id)

    db.refresh(acquisition_plan)
    assert acquisition_plan.schedule != []


def test_check_to_schedule_acquisition_different_storage_location(db: Session) -> None:
    acquisition_plan = create_random_acquisition_plan(
        session=db, storage_location=Location.HOTEL
    )
    assert acquisition_plan.schedule == []

    wellplate = acquisition_plan.wellplate
    assert wellplate.location == Location.EXTERNAL
    wellplate_in = WellplateUpdate(location=Location.CYTOMAT2)
    labware_crud.update_wellplate(
        session=db, db_wellplate=wellplate, wellplate_in=wellplate_in
    )

    resource_id = f"wellplate.{wellplate.name}"
    check_to_schedule_acquisition(resource_id=resource_id)

    db.refresh(acquisition_plan)
    # plate is not present in acquisition plan's storage_location, so scheduling
    # does not occur.
    assert acquisition_plan.schedule == []


def test_check_to_schedule_acquisition_no_wellplate() -> None:
    resource_id = "wellplate.nonexist"
    with pytest.raises(ValueError):
        check_to_schedule_acquisition(resource_id=resource_id)


def test_check_to_schedule_acquisition_invalid_resource_id() -> None:
    resource_id = "welplate.badprefix"
    with pytest.raises(
        ValueError, match=f"Invalid wellplate resource id: {resource_id}"
    ):
        check_to_schedule_acquisition(resource_id=resource_id)

    resource_id = "wellplate.contains.dots"
    with pytest.raises(
        ValueError, match=f"Invalid wellplate resource id: {resource_id}"
    ):
        check_to_schedule_acquisition(resource_id=resource_id)

    resource_id = "wellplate.contains spaces"
    with pytest.raises(
        ValueError, match=f"Invalid wellplate resource id: {resource_id}"
    ):
        check_to_schedule_acquisition(resource_id=resource_id)

    resource_id = "wellplate.contains-non_word-chars"
    with pytest.raises(
        ValueError, match=f"Invalid wellplate resource id: {resource_id}"
    ):
        check_to_schedule_acquisition(resource_id=resource_id)
