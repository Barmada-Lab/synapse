from sqlmodel import Session, select

from .models import (
    Acquisition,
    AcquisitionCreate,
    ArtifactCollection,
    ArtifactCollectionCreate,
)


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
