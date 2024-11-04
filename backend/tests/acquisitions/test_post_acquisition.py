from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import patch

import pytest

from app.acquisitions.flows import post_acquisition_flow
from app.common.errors import AggregateError
from app.core.config import settings


@pytest.mark.asyncio
async def test_post_acquisition_flow(random_acquisition_dir: Path):
    experiment_id = random_acquisition_dir.name

    acquisition_path = settings.ACQUISITION_DIR / experiment_id
    analysis_path = settings.ANALYSIS_DIR / experiment_id
    archive_path = settings.ARCHIVE_DIR / f"{experiment_id}.tar.zst"

    assert acquisition_path.exists()
    assert not analysis_path.exists()
    assert not archive_path.exists()

    await post_acquisition_flow(experiment_id=experiment_id)

    assert not acquisition_path.exists()
    assert analysis_path.exists()
    assert archive_path.exists()


@pytest.mark.asyncio
async def test_post_acquisition_flow_raises_not_a_directory_error(
    random_acquisition_file: Path,
):
    experiment_id = random_acquisition_file.name
    with pytest.raises(NotADirectoryError):
        await post_acquisition_flow(experiment_id=experiment_id)


@pytest.mark.asyncio
async def test_post_acquisition_flow_raises_not_found_error():
    experiment_id = "not_found"
    with pytest.raises(FileNotFoundError):
        await post_acquisition_flow(experiment_id=experiment_id)


@pytest.mark.asyncio
async def test_post_acquisition_flow_raises_path_traversal_error(
    random_acquisition_dir: Path,
):
    experiment_id = f"../{random_acquisition_dir.name}"
    with pytest.raises(ValueError):
        await post_acquisition_flow(experiment_id=experiment_id)


def create_file_and_raise_error(path: Path):
    def _run(*_args, **_kwargs):
        path.touch()
        raise CalledProcessError(1, "mock")

    return _run


@pytest.mark.asyncio
async def test_post_acquisition_flow_sync_fails(
    random_acquisition_dir: Path,
):
    experiment_id = random_acquisition_dir.name

    acquisition_path = settings.ACQUISITION_DIR / experiment_id
    analysis_path = settings.ANALYSIS_DIR / experiment_id
    archive_path = settings.ARCHIVE_DIR / f"{experiment_id}.tar.zst"

    assert acquisition_path.exists()
    assert not analysis_path.exists()
    assert not archive_path.exists()

    with patch("app.acquisitions.flows._sync_cmd") as mock_sync:
        mock_sync.side_effect = create_file_and_raise_error(analysis_path)
        with pytest.raises(AggregateError):
            await post_acquisition_flow(experiment_id=experiment_id)

    assert (
        acquisition_path.exists()
    ), "Acquisition path should not be deleted if sync fails"
    assert archive_path.exists(), "Archive path should created even if sync fails"


@pytest.mark.asyncio
async def test_post_acquisition_flow_archive_fails(
    random_acquisition_dir: Path,
):
    experiment_id = random_acquisition_dir.name

    acquisition_path = settings.ACQUISITION_DIR / experiment_id
    analysis_path = settings.ANALYSIS_DIR / experiment_id
    archive_path = settings.ARCHIVE_DIR / f"{experiment_id}.tar.zst"

    assert acquisition_path.exists()
    assert not analysis_path.exists()
    assert not archive_path.exists()

    with patch("app.acquisitions.flows._archive_cmd") as mock_archive:
        mock_archive.side_effect = create_file_and_raise_error(archive_path)
        with pytest.raises(AggregateError):
            await post_acquisition_flow(experiment_id=experiment_id)

    assert (
        acquisition_path.exists()
    ), "Acquisition path should not be deleted if archiving fails"
    assert (
        analysis_path.exists()
    ), "Analysis path should be created even if archiving fails"


@pytest.mark.asyncio
async def test_post_acquisition_flow_sync_and_archive_fails(
    random_acquisition_dir: Path,
):
    acquisition_path = settings.ACQUISITION_DIR / random_acquisition_dir.name
    analysis_path = settings.ANALYSIS_DIR / random_acquisition_dir.name
    archive_path = settings.ARCHIVE_DIR / f"{random_acquisition_dir.name}.tar.zst"

    with (
        patch("app.acquisitions.flows._sync_cmd") as mock_sync,
        patch("app.acquisitions.flows._archive_cmd") as mock_archive,
    ):
        mock_sync.side_effect = create_file_and_raise_error(analysis_path)
        mock_archive.side_effect = create_file_and_raise_error(archive_path)
        with pytest.raises(AggregateError):
            await post_acquisition_flow(experiment_id=random_acquisition_dir.name)

    assert (
        acquisition_path.exists()
    ), "Acquisition path should not be deleted if sync fails"
