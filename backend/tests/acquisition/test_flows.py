from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import patch

import pytest
from sqlmodel import Session

from app.acquisition import crud
from app.acquisition.flows.acquisition_scheduling import check_to_schedule_acquisition
from app.acquisition.flows.plateread_postprocessing import handle_post_acquisition
from app.acquisition.models import (
    ArtifactType,
    Repository,
    SlurmJobStatus,
    get_artifact_collection_path,
)
from app.common.errors import AggregateError
from app.labware import crud as labware_crud
from app.labware.models import Location, WellplateUpdate
from tests.acquisition.utils import (
    create_random_acquisition_plan,
    create_random_analysis_spec,
    create_random_artifact_collection,
)


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow(db: Session):
    acquisition_artifacts = create_random_artifact_collection(session=db)
    acquisition_name = acquisition_artifacts.acquisition.name

    assert acquisition_artifacts.path.exists()

    await handle_post_acquisition(acquisition_name=acquisition_name)

    assert not acquisition_artifacts.path.exists()
    archive_artifacts = crud.get_artifact_collection_by_key(
        session=db,
        acquisition_id=acquisition_artifacts.acquisition_id,
        key=(Repository.ARCHIVE, ArtifactType.ACQUISITION),
    )
    assert archive_artifacts
    assert archive_artifacts.path.exists()

    analysis_artifacts = crud.get_artifact_collection_by_key(
        session=db,
        acquisition_id=acquisition_artifacts.acquisition_id,
        key=(Repository.ANALYSIS, ArtifactType.ACQUISITION),
    )
    assert analysis_artifacts
    assert analysis_artifacts.path.exists()


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_raises_not_found_error():
    acquisition_name = "not_found"
    with pytest.raises(ValueError, match=f"Acquisition {acquisition_name} not found"):
        await handle_post_acquisition(acquisition_name=acquisition_name)


def create_file_and_raise_error(path: Path):
    def _run(*_args, **_kwargs):
        path.touch()
        raise CalledProcessError(1, "mocked create_file_and_raise_error")

    return _run


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_sync_fails(db: Session):
    acquisition_artifacts = create_random_artifact_collection(session=db)
    acquisition_name = acquisition_artifacts.acquisition.name

    analysis_path = get_artifact_collection_path(
        Repository.ARCHIVE, acquisition_name, ArtifactType.ACQUISITION
    )

    with patch("app.acquisition.flows.plateread_postprocessing._sync_cmd") as mock_sync:
        mock_sync.side_effect = create_file_and_raise_error(analysis_path)
        with pytest.raises(AggregateError):
            await handle_post_acquisition(acquisition_name=acquisition_name)

    assert (
        acquisition_artifacts.path.exists()
    ), "Acquisition artifact collection should not be deleted if archive fails"

    archive_artifacts = crud.get_artifact_collection_by_key(
        session=db,
        acquisition_id=acquisition_artifacts.acquisition_id,
        key=(Repository.ARCHIVE, ArtifactType.ACQUISITION),
    )
    assert not archive_artifacts

    analysis_artifacts = crud.get_artifact_collection_by_key(
        session=db,
        acquisition_id=acquisition_artifacts.acquisition_id,
        key=(Repository.ANALYSIS, ArtifactType.ACQUISITION),
    )
    assert not analysis_artifacts


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_archive_fails(db: Session):
    acquisition_artifacts = create_random_artifact_collection(session=db)
    acquisition_name = acquisition_artifacts.acquisition.name

    archive_path = get_artifact_collection_path(
        Repository.ARCHIVE, acquisition_name, ArtifactType.ACQUISITION
    )

    with patch(
        "app.acquisition.flows.plateread_postprocessing._archive_cmd"
    ) as mock_archive:
        mock_archive.side_effect = create_file_and_raise_error(archive_path)
        with pytest.raises(AggregateError):
            await handle_post_acquisition(acquisition_name=acquisition_name)

    assert (
        acquisition_artifacts.path.exists()
    ), "Acquisition artifact collection should not be deleted if archive fails"

    archive_artifacts = crud.get_artifact_collection_by_key(
        session=db,
        acquisition_id=acquisition_artifacts.acquisition_id,
        key=(Repository.ARCHIVE, ArtifactType.ACQUISITION),
    )
    assert not archive_artifacts

    analysis_artifacts = crud.get_artifact_collection_by_key(
        session=db,
        acquisition_id=acquisition_artifacts.acquisition_id,
        key=(Repository.ANALYSIS, ArtifactType.ACQUISITION),
    )
    assert not analysis_artifacts


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_submits_analyses_if_present(db: Session):
    # test with/without analysis plan-
    # should be using "assert_called_once_with," but I can't figure out how
    # to mock uuid4 in prefect.events.schema.events
    acquisition_artifacts = create_random_artifact_collection(session=db)
    acquisition = acquisition_artifacts.acquisition
    analysis_spec = create_random_analysis_spec(session=db, acquisition=acquisition)

    assert analysis_spec.status == SlurmJobStatus.UNSUBMITTED

    with patch(
        "app.acquisition.flows.plateread_postprocessing.emit_event"
    ) as mock_emit:
        await handle_post_acquisition(acquisition_name=acquisition.name)
        mock_emit.assert_called_once()
        db.refresh(analysis_spec)
        assert analysis_spec.status == SlurmJobStatus.SUBMITTED


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_no_analysis(db: Session):
    acquisition_artifacts = create_random_artifact_collection(session=db)
    acquisition = acquisition_artifacts.acquisition
    with patch(
        "app.acquisition.flows.plateread_postprocessing.emit_event"
    ) as mock_emit:
        await handle_post_acquisition(acquisition_name=acquisition.name)
        mock_emit.assert_not_called()


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
