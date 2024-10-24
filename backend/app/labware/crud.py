from sqlmodel import Session, select

from .models import Wellplate, WellplateCreate, WellplateUpdate


def create_wellplate(
    *, session: Session, wellplate_create: WellplateCreate
) -> Wellplate:
    db_obj = Wellplate.model_validate(wellplate_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_wellplate(
    *, session: Session, db_wellplate: Wellplate, wellplate_in: WellplateUpdate
) -> Wellplate:
    well_plate_data = wellplate_in.model_dump(exclude_unset=True)
    db_wellplate.sqlmodel_update(well_plate_data)
    session.add(db_wellplate)
    session.commit()
    session.refresh(db_wellplate)
    return db_wellplate


def get_wellplate_by_name(*, session: Session, name: str) -> Wellplate | None:
    statement = select(Wellplate).where(Wellplate.name == name)
    session_well_plate = session.exec(statement).first()
    return session_well_plate
