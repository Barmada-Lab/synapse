from datetime import datetime

from sqlmodel import Session, select

from app.labware.models import Wellplate

from .models import (
    Acquisition,
    AcquisitionCreate,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    Artifact,
    ArtifactCollection,
    ArtifactCollectionCreate,
    ArtifactCreate,
    ArtifactType,
    PlatereadSpec,
    PlatereadSpecUpdate,
    Repository,
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
    db_plateread.sqlmodel_update(plateread_data)
    session.add(db_plateread)
    session.commit()
    return db_plateread


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


def get_artifact_collection_by_key(
    *, session: Session, acquisition_id: int, key: tuple[Repository, ArtifactType]
) -> ArtifactCollection | None:
    statement = select(ArtifactCollection).where(
        ArtifactCollection.acquisition_id == acquisition_id
        and ArtifactCollection.location == key[0]
        and ArtifactCollection.artifact_type == key[1]
    )
    return session.exec(statement).first()


def create_artifact(
    *, session: Session, artifact_collection_id: int, artifact_create: ArtifactCreate
) -> Artifact:
    collection_obj = session.get(ArtifactCollection, artifact_collection_id)
    if collection_obj is None:
        raise ValueError("Collection not found")
    db_obj = Artifact.model_validate(
        artifact_create, update={"collection_id": artifact_collection_id}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


# TODO: write tests
# def create_artifact_collection_replica(
#     *, session: Session, artifact_collection: ArtifactCollection, location: Repository
# ) -> ArtifactCollection:
#     other_artifact_collections = artifact_collection.acquisition.collections
#     if artifact_collection.location == location or any(
#         other.location == location for other in other_artifact_collections
#     ):
#         raise ValueError("Duplicate artifact collection!")
#     create = ArtifactCollectionCreate(
#         location=location,
#         artifact_type=artifact_collection.artifact_type,
#         acquisition_id=artifact_collection.acquisition_id,
#     )
#     created = create_artifact_collection(session=session, artifact_collection_create=create)
#     for artifact in artifact_collection.artifacts:
#         create_artifact(
#             session=session,
#             artifact_collection_id=created.id,  # type: ignore
#             artifact_create=ArtifactCreate(
#                 name=artifact.name,
#             ),
#         )
#     return created
