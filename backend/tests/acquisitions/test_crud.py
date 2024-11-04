import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.acquisitions import crud
from app.acquisitions.models import (
    AcquisitionCreate,
    ArtifactCollectionCreate,
    ArtifactType,
    Repository,
)
from tests.utils import random_lower_string


def test_create_acquisition(db: Session) -> None:
    name = random_lower_string()
    acquisition_create = AcquisitionCreate(name=name)

    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )
    assert acquisition.name == name


def test_create_acquisition_already_exists(db: Session) -> None:
    name = random_lower_string()
    acquisition_create = AcquisitionCreate(name=name)

    _ = crud.create_acquisition(session=db, acquisition_create=acquisition_create)
    with pytest.raises(IntegrityError):
        crud.create_acquisition(session=db, acquisition_create=acquisition_create)
    db.rollback()


def test_get_acquisition_by_name(db: Session) -> None:
    name = random_lower_string()
    acquisition_create = AcquisitionCreate(name=name)

    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )
    stored_acquisition = crud.get_acquisition_by_name(session=db, name=name)
    assert stored_acquisition is not None
    assert acquisition.name == stored_acquisition.name


def test_get_acquisition_by_name_not_found(db: Session) -> None:
    name = random_lower_string()
    stored_acquisition = crud.get_acquisition_by_name(session=db, name=name)
    assert stored_acquisition is None


def test_create_artifact_collection(db: Session) -> None:
    acquisition_create = AcquisitionCreate(name=random_lower_string())
    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )

    acquisition_id = acquisition.id
    location = Repository.ACQUISITION
    artifact_type = ArtifactType.ACQUISITION
    artifact_collection_create = ArtifactCollectionCreate(
        location=location,
        artifact_type=artifact_type,
        acquisition_id=acquisition_id,
    )

    artifact = crud.create_artifact_collection(
        session=db, artifact_collection_create=artifact_collection_create
    )
    assert artifact.location == location
    assert artifact.artifact_type == artifact_type
    assert artifact.acquisition_id == acquisition_id

    db.refresh(acquisition)
    assert acquisition.collections[0].id == artifact.id


def test_create_artifact_collection_invalid_acquisition_id(db: Session) -> None:
    acquisition_id = 2**16
    artifact_collection_create = ArtifactCollectionCreate(
        location=Repository.ACQUISITION,
        artifact_type=ArtifactType.ACQUISITION,
        acquisition_id=acquisition_id,
    )

    with pytest.raises(ValueError) as e:
        crud.create_artifact_collection(
            session=db, artifact_collection_create=artifact_collection_create
        )
        assert "Acquisition not found" in str(e)


def test_create_artifact_duplicate_type_and_location(db: Session) -> None:
    """Each combination of ArtifactType and Repository should be unique"""
    acquisition_create = AcquisitionCreate(name=random_lower_string())
    acquisition = crud.create_acquisition(
        session=db, acquisition_create=acquisition_create
    )

    acquisition_id = acquisition.id
    location = Repository.ACQUISITION
    artifact_type = ArtifactType.ACQUISITION
    artifact_collection_create = ArtifactCollectionCreate(
        location=location,
        artifact_type=artifact_type,
        acquisition_id=acquisition_id,
    )

    _ = crud.create_artifact_collection(
        session=db, artifact_collection_create=artifact_collection_create
    )
    with pytest.raises(ValueError) as e:
        crud.create_artifact_collection(
            session=db, artifact_collection_create=artifact_collection_create
        )
        assert "Duplicate artifact collection" in str(e)
