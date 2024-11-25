from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import patch

import pytest
from sqlmodel import Session

from app.acquisition.flows.acquisition_scheduling import check_to_schedule_acquisition
from app.acquisition.flows.plateread_postprocessing import handle_post_acquisition
from app.common.errors import AggregateError
from app.core.config import settings
from app.labware import crud as labware_crud
from app.labware.models import Location, WellplateUpdate
from tests.acquisition.utils import create_random_acquisition_plan


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow(random_acquisition_dir: Path):
    acquisition_name = random_acquisition_dir.name

    acquisition_path = settings.ACQUISITION_DIR / acquisition_name
    analysis_path = settings.ANALYSIS_DIR / acquisition_name
    archive_path = settings.ARCHIVE_DIR / f"{acquisition_name}.tar.zst"

    assert acquisition_path.exists()
    assert not analysis_path.exists()
    assert not archive_path.exists()

    await handle_post_acquisition(acquisition_name=acquisition_name)

    assert not acquisition_path.exists()
    assert analysis_path.exists()
    assert archive_path.exists()


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_raises_not_found_error():
    acquisition_name = "not_found"
    with pytest.raises(FileNotFoundError):
        await handle_post_acquisition(acquisition_name=acquisition_name)


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_raises_path_traversal_error(
    random_acquisition_dir: Path,
):
    acquisition_name = f"../{random_acquisition_dir.name}"
    with pytest.raises(ValueError):
        await handle_post_acquisition(acquisition_name=acquisition_name)


def create_file_and_raise_error(path: Path):
    def _run(*_args, **_kwargs):
        path.touch()
        raise CalledProcessError(1, "mocked create_file_and_raise_error")

    return _run


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_sync_fails(
    random_acquisition_dir: Path,
):
    acquisition_name = random_acquisition_dir.name

    acquisition_path = settings.ACQUISITION_DIR / acquisition_name
    analysis_path = settings.ANALYSIS_DIR / acquisition_name
    archive_path = settings.ARCHIVE_DIR / f"{acquisition_name}.tar.zst"

    assert acquisition_path.exists()
    assert not analysis_path.exists()
    assert not archive_path.exists()

    with patch("app.acquisition.flows.plateread_postprocessing._sync_cmd") as mock_sync:
        mock_sync.side_effect = create_file_and_raise_error(analysis_path)
        with pytest.raises(AggregateError):
            await handle_post_acquisition(acquisition_name=acquisition_name)

    assert (
        acquisition_path.exists()
    ), "Acquisition path should not be deleted if sync fails"
    assert archive_path.exists(), "Archive path should created even if sync fails"


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_archive_fails(
    random_acquisition_dir: Path,
):
    acquisition_name = random_acquisition_dir.name

    acquisition_path = settings.ACQUISITION_DIR / acquisition_name
    analysis_path = settings.ANALYSIS_DIR / acquisition_name
    archive_path = settings.ARCHIVE_DIR / f"{acquisition_name}.tar.zst"

    assert acquisition_path.exists()
    assert not analysis_path.exists()
    assert not archive_path.exists()

    with patch(
        "app.acquisition.flows.plateread_postprocessing._archive_cmd"
    ) as mock_archive:
        mock_archive.side_effect = create_file_and_raise_error(archive_path)
        with pytest.raises(AggregateError):
            await handle_post_acquisition(acquisition_name=acquisition_name)

    assert (
        acquisition_path.exists()
    ), "Acquisition path should not be deleted if archiving fails"
    assert (
        analysis_path.exists()
    ), "Analysis path should be created even if archiving fails"


@pytest.mark.asyncio
async def test_handle_post_acquisition_flow_sync_and_archive_fails(
    random_acquisition_dir: Path,
):
    acquisition_path = settings.ACQUISITION_DIR / random_acquisition_dir.name
    analysis_path = settings.ANALYSIS_DIR / random_acquisition_dir.name
    archive_path = settings.ARCHIVE_DIR / f"{random_acquisition_dir.name}.tar.zst"

    with (
        patch("app.acquisition.flows.plateread_postprocessing._sync_cmd") as mock_sync,
        patch(
            "app.acquisition.flows.plateread_postprocessing._archive_cmd"
        ) as mock_archive,
    ):
        mock_sync.side_effect = create_file_and_raise_error(analysis_path)
        mock_archive.side_effect = create_file_and_raise_error(archive_path)
        with pytest.raises(AggregateError):
            await handle_post_acquisition(acquisition_name=random_acquisition_dir.name)

    assert (
        acquisition_path.exists()
    ), "Acquisition path should not be deleted if sync fails"


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
