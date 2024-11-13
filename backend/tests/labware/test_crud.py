import pytest
from pydantic import ValidationError
from sqlmodel import Session

from app.labware import crud
from app.labware.models import (
    Location,
    Wellplate,
    WellplateCreate,
    WellplateType,
    WellplateUpdate,
)
from tests.utils import random_lower_string


def test_create_wellplate(db: Session) -> None:
    name = random_lower_string(9)
    well_plate_in = WellplateCreate(
        name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96
    )
    well_plate = crud.create_wellplate(session=db, wellplate_create=well_plate_in)
    assert well_plate.name == well_plate_in.name
    assert well_plate.plate_type == well_plate_in.plate_type


def test_create_wellplate_empty_name() -> None:
    name = ""
    with pytest.raises(ValidationError):
        _ = WellplateCreate(name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96)


def test_create_wellplate_long_name():
    name = random_lower_string(10)
    with pytest.raises(ValidationError):
        _ = WellplateCreate(name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96)


def test_update_wellplate(db: Session) -> None:
    name = random_lower_string(9)
    well_plate_in = WellplateCreate(
        name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96
    )
    wellplate = crud.create_wellplate(session=db, wellplate_create=well_plate_in)
    orig_loc = wellplate.location

    update_location_in = WellplateUpdate(location=Location.CQ1)
    crud.update_wellplate(
        session=db, db_wellplate=wellplate, wellplate_in=update_location_in
    )

    updated = db.get_one(Wellplate, wellplate.id)
    assert orig_loc != updated.location


def test_get_wellplate_by_name(db: Session) -> None:
    name = random_lower_string(9)
    well_plate_in = WellplateCreate(
        name=name, plate_type=WellplateType.REVVITY_PHENOPLATE_96
    )
    well_plate = crud.create_wellplate(session=db, wellplate_create=well_plate_in)

    other_well_plate = crud.get_wellplate_by_name(session=db, name=name)
    assert other_well_plate == well_plate
