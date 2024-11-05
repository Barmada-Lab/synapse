from datetime import datetime

from sqlmodel import Session, select

from app.labware.models import Wellplate

from .models import (
    Acquisition,
    AcquisitionCreate,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    ArtifactCollection,
    ArtifactCollectionCreate,
    PlatereadSpec,
    PlatereadSpecUpdate,
)


def create_acquisition_plan(
    *, session: Session, plan_create: AcquisitionPlanCreate
) -> AcquisitionPlan:
    wellplate_id = plan_create.wellplate_id
    if session.get(Wellplate, wellplate_id) is None:
        raise ValueError(f"Wellplate {wellplate_id} not found")

    acquisition_plan = AcquisitionPlan.model_validate(plan_create)
    session.add(acquisition_plan)
    session.commit()
    session.refresh(acquisition_plan)
    return acquisition_plan


def get_acquisition_plan_by_name(
    *, session: Session, name: str
) -> AcquisitionPlan | None:
    stmt = select(AcquisitionPlan).where(AcquisitionPlan.name == name)
    return session.exec(stmt).first()


def schedule_plan(*, session: Session, plan: AcquisitionPlan) -> AcquisitionPlan:
    start_time = datetime.now()
    for i in range(plan.n_reads):
        start_after = start_time + (i * plan.interval)
        deadline = start_time + i * plan.interval + plan.deadline_delta
        session.add(
            PlatereadSpec(
                start_after=start_after,
                deadline=deadline,
                acquisition_plan_id=plan.id,
            )
        )
    session.commit()
    session.refresh(plan)
    return plan


def update_plateread(
    *,
    session: Session,
    db_plateread: PlatereadSpec,
    plateread_in: PlatereadSpecUpdate,
) -> PlatereadSpec:
    plateread_data = plateread_in.model_dump(exclude_unset=True)
    db_obj = db_plateread.model_copy()
    db_obj.sqlmodel_update(plateread_data)
    session.add(db_obj)
    session.commit()
    return db_obj


def create_acquisition(
    *, session: Session, acquisition_create: AcquisitionCreate
) -> Acquisition:
    db_obj = Acquisition.model_validate(acquisition_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_acquisition_by_name(*, session: Session, name: str) -> Acquisition | None:
    statement = select(Acquisition).where(Acquisition.name == name)
    db_obj = session.exec(statement).first()
    return db_obj


def create_artifact_collection(
    *, session: Session, artifact_collection_create: ArtifactCollectionCreate
) -> ArtifactCollection:
    acquisition_obj = session.get(
        Acquisition, artifact_collection_create.acquisition_id
    )
    if acquisition_obj is None:
        raise ValueError("Acquisition not found")
    for collection in acquisition_obj.collections:
        if (
            artifact_collection_create.location == collection.location
            and artifact_collection_create.artifact_type == collection.artifact_type
        ):
            raise ValueError("Duplicate artifact collection")
    db_obj = ArtifactCollection.model_validate(artifact_collection_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj
