from sqlmodel import Session, select

from .models import WellPlate, WellPlateCreate, WellPlateUpdate


def create_wellplate(
    *, session: Session, well_plate_create: WellPlateCreate
) -> WellPlate:
    db_obj = WellPlate.model_validate(well_plate_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_wellplate(
    *, session: Session, db_well_plate: WellPlate, well_plate_in: WellPlateUpdate
) -> WellPlate:
    well_plate_data = well_plate_in.model_dump(exclude_unset=True)
    db_well_plate.sqlmodel_update(well_plate_data)
    session.add(db_well_plate)
    session.commit()
    session.refresh(db_well_plate)
    return db_well_plate


def get_wellplate_by_name(*, session: Session, name: str) -> WellPlate | None:
    statement = select(WellPlate).where(WellPlate.name == name)
    session_well_plate = session.exec(statement).first()
    return session_well_plate
