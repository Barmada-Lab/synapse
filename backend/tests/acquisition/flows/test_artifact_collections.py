from subprocess import CalledProcessError
from unittest.mock import patch

import pytest
from returns.io import IOFailure
from returns.primitives.exceptions import UnwrapFailedError
from sqlmodel import Session

from app.acquisition.flows.artifact_collections import (
    copy_collection,
    move_collection,
)
from app.acquisition.models import ArtifactType, Repository
from tests.acquisition.utils import create_random_artifact_collection


def test_copy_acquisition_to_analysis(db: Session):
    collection = create_random_artifact_collection(
        location=Repository.ACQUISITION_STORE, session=db
    )
    new_collection = copy_collection(
        collection=collection, dest=Repository.ANALYSIS_STORE, session=db
    )
    assert new_collection.location == Repository.ANALYSIS_STORE
    assert new_collection.path.exists()


def test_copy_analysis_to_acquisition(db: Session):
    collection = create_random_artifact_collection(
        location=Repository.ANALYSIS_STORE, session=db
    )
    new_collection = copy_collection(
        collection=collection, dest=Repository.ACQUISITION_STORE, session=db
    )
    assert new_collection.location == Repository.ACQUISITION_STORE
    assert new_collection.path.exists()


def test_copy_acquisition_to_archive(db: Session):
    collection = create_random_artifact_collection(
        location=Repository.ACQUISITION_STORE, session=db
    )
    new_collection = copy_collection(
        collection=collection, dest=Repository.ARCHIVE_STORE, session=db
    )
    assert new_collection.location == Repository.ARCHIVE_STORE
    assert new_collection.path.exists()


def test_copy_archive_to_acquisition(db: Session):
    collection = create_random_artifact_collection(
        location=Repository.ANALYSIS_STORE, session=db
    )
    # move to archive first
    collection = copy_collection(
        collection=collection, dest=Repository.ARCHIVE_STORE, session=db
    )
    new_collection = copy_collection(
        collection=collection, dest=Repository.ACQUISITION_STORE, session=db
    )
    assert new_collection.location == Repository.ACQUISITION_STORE
    assert new_collection.path.exists()


def test_copy_analysis_to_archive(db: Session):
    collection = create_random_artifact_collection(
        location=Repository.ANALYSIS_STORE, session=db
    )
    new_collection = copy_collection(
        collection=collection, dest=Repository.ARCHIVE_STORE, session=db
    )
    assert new_collection.location == Repository.ARCHIVE_STORE
    assert new_collection.path.exists()


def test_copy_archive_to_analysis(db: Session):
    collection = create_random_artifact_collection(
        location=Repository.ACQUISITION_STORE, session=db
    )
    # move to archive first
    collection = copy_collection(
        collection=collection, dest=Repository.ARCHIVE_STORE, session=db
    )
    new_collection = copy_collection(
        collection=collection, dest=Repository.ANALYSIS_STORE, session=db
    )
    assert new_collection.location == Repository.ANALYSIS_STORE
    assert new_collection.path.exists()


def test_copy_collection_same_location(db: Session):
    collection = create_random_artifact_collection(
        location=Repository.ACQUISITION_STORE, session=db
    )
    with pytest.raises(ValueError):
        copy_collection(
            collection=collection, dest=Repository.ACQUISITION_STORE, session=db
        )


def test_copy_collection_transfer_fails(db: Session):
    orig_collection = create_random_artifact_collection(
        location=Repository.ACQUISITION_STORE, session=db
    )
    acquisition = orig_collection.acquisition
    with patch("app.acquisition.flows.artifact_collections.run_subprocess") as mock:
        mock.return_value = IOFailure.from_failure(
            CalledProcessError(1, "mocked run_subprocess")
        )
        try:
            copy_collection(
                collection=orig_collection, dest=Repository.ANALYSIS_STORE, session=db
            )
        except UnwrapFailedError:
            pass

        assert not acquisition.get_collection(
            ArtifactType.ACQUISITION_DATA, Repository.ANALYSIS_STORE
        )


def test_move_collection(db: Session):
    orig_collection = create_random_artifact_collection(
        location=Repository.ACQUISITION_STORE, session=db
    )
    # move to archive first
    new_collection = move_collection(
        collection=orig_collection, dest=Repository.ANALYSIS_STORE, session=db
    )

    assert new_collection.location == Repository.ANALYSIS_STORE
    assert new_collection.path.exists()
    assert not orig_collection.path.exists()


def test_move_collection_transfer_fails(db: Session):
    orig_collection = create_random_artifact_collection(
        location=Repository.ACQUISITION_STORE, session=db
    )
    _ = orig_collection.acquisition
    with patch("app.acquisition.flows.artifact_collections.run_subprocess") as mock:
        mock.return_value = IOFailure.from_failure(
            CalledProcessError(1, "mocked run_subprocess")
        )
        try:
            move_collection(
                collection=orig_collection, dest=Repository.ANALYSIS_STORE, session=db
            )
        except UnwrapFailedError:
            pass

        assert orig_collection.path.exists()
