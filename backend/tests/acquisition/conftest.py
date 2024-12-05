import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from prefect.testing.utilities import prefect_test_harness

from app.core.config import settings


@pytest.fixture(autouse=True, scope="module")
def prefect_test_fixture():
    with prefect_test_harness():
        yield


@pytest.fixture(scope="session", autouse=True)
def acquisition_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tempdir:
        settings.ACQUISITION_DIR = Path(tempdir)
        yield Path(tempdir)


@pytest.fixture(scope="session", autouse=True)
def analysis_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tempdir:
        settings.ANALYSIS_DIR = Path(tempdir)
        yield Path(tempdir)


@pytest.fixture(scope="session", autouse=True)
def archive_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tempdir:
        settings.ARCHIVE_DIR = Path(tempdir)
        yield Path(tempdir)


@pytest.fixture(scope="session", autouse=True)
def overlord_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tempdir:
        settings.OVERLORD_DIR = Path(tempdir)
        (settings.OVERLORD_DIR / "Batches" / "Kiosk").mkdir(parents=True, exist_ok=True)
        (settings.OVERLORD_DIR / "Batches" / "Queued").mkdir(exist_ok=True)
        (settings.OVERLORD_DIR / "Batches" / "Archive").mkdir(exist_ok=True)
        (settings.OVERLORD_DIR / "Batches" / "Running").mkdir(exist_ok=True)
        yield Path(tempdir)
