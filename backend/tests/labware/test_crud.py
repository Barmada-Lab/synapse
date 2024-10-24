from sqlmodel import Session

from app.labware import crud
from app.labware.models import Location, WellplateCreate, WellplateType, WellplateUpdate
from tests.utils import random_lower_string


def test_create_wellplate(db: Session) -> None:
    name = random_lower_string()
    well_plate_in = WellplateCreate(
        name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96
    )
    well_plate = crud.create_wellplate(session=db, wellplate_create=well_plate_in)
    assert well_plate.name == well_plate_in.name
    assert well_plate.plate_type == well_plate_in.plate_type


def test_update_wellplate_updates_last_updated(db: Session) -> None:
    name = random_lower_string()
    well_plate_in = WellplateCreate(
        name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96
    )
    well_plate = crud.create_wellplate(session=db, wellplate_create=well_plate_in)

    last_last_update = well_plate.last_update

    update_location_in = WellplateUpdate(location=Location.CQ1)
    well_plate = crud.update_wellplate(
        session=db, db_wellplate=well_plate, wellplate_in=update_location_in
    )
    assert well_plate.last_update > last_last_update


def test_update_wellplate_with_same_values_doesnt_change_last_updated(
    db: Session,
) -> None:
    name = random_lower_string()

    # is None, update to None
    well_plate_in = WellplateCreate(
        name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96
    )
    well_plate = crud.create_wellplate(session=db, wellplate_create=well_plate_in)

    assert well_plate.location is None

    last_last_update = well_plate.last_update

    update_location_in = WellplateUpdate(location=None)
    well_plate = crud.update_wellplate(
        session=db, db_wellplate=well_plate, wellplate_in=update_location_in
    )
    assert well_plate.last_update == last_last_update

    # is Some(Location.CQ1), update to Some(Location.CQ1)
    update_location_in = WellplateUpdate(location=Location.CQ1)
    well_plate = crud.update_wellplate(
        session=db, db_wellplate=well_plate, wellplate_in=update_location_in
    )

    last_last_update = well_plate.last_update

    update_location_in = WellplateUpdate(location=Location.CQ1)
    well_plate = crud.update_wellplate(
        session=db, db_wellplate=well_plate, wellplate_in=update_location_in
    )
    assert well_plate.last_update == last_last_update


def test_get_wellplate_by_name(db: Session) -> None:
    name = random_lower_string()
    well_plate_in = WellplateCreate(
        name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96
    )
    well_plate = crud.create_wellplate(session=db, wellplate_create=well_plate_in)

    other_well_plate = crud.get_wellplate_by_name(session=db, name=name)
    assert other_well_plate == well_plate
