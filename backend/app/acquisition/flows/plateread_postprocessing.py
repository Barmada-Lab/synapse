import asyncio
import logging
import os
import platform
import re
import shutil
from pathlib import Path

from prefect import flow, task
from pydantic import DirectoryPath

from app.acquisition.events import PLATEREAD_RESOURCE_REGEX
from app.acquisition.models import (
    PlatereadSpec,
    ProcessStatus,
)
from app.common.errors import AggregateError
from app.common.proc import run_subproc_async
from app.core.config import settings
from app.core.deps import get_db

logger = logging.getLogger(__name__)


async def _sync_cmd(origin: Path, dest: DirectoryPath):
    await run_subproc_async(f"rsync -r {origin} {dest}", check=True)


def cleanup(path: Path):
    logger.info("Cleaning up %s", path)
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            os.remove(path)
    except Exception as e:
        logger.error(f"Error cleaning up {path}: {e}")
        raise e


@task
async def sync(origin: Path, dest: DirectoryPath):
    # call separated to allow mocking
    await _sync_cmd(origin, dest)


async def _archive_cmd(dest_zst: Path, origin: DirectoryPath):
    match platform.system():
        case "Linux":
            await run_subproc_async(
                f"tar -c -I 'zstd -T4' -f {dest_zst} -C {origin.parent} \
                    {origin.name}",
                check=True,
            )
        case "Darwin":
            await run_subproc_async(
                f"tar -c --zstd --options 'zstd:compression-level=4' \
                    -f {dest_zst} -C {origin.parent} {origin.name}",
                check=True,
            )


@task
async def archive(origin: DirectoryPath, dest: DirectoryPath):
    dest_zst = dest / f"{origin.name}.tar.zst"
    # call separated to allow mocking
    await _archive_cmd(dest_zst, origin)


@task
def rmtree(local_dir: Path):
    shutil.rmtree(local_dir)


@task
def verify_acquisition_dir(_local_dir: Path):
    if not _local_dir.is_dir():
        raise FileNotFoundError(f"Acquisition directory {_local_dir} not found")


@flow
async def handle_post_acquisition(acquisition_name: str):
    # TODO: create acquisition collections as platereads complete
    # with get_db() as session:
    #     acquisition = crud.get_acquisition_by_name(
    #         session=session, name=acquisition_name
    #     )
    #     if not acquisition:
    #         raise ValueError(f"Acquisition {acquisition_name} not found")

    #     acquisition_collection = crud.get_artifact_collection_by_key(
    #         session=session,
    #         acquisition_id=acquisition.id, # type: ignore
    #         key=(Repository.ACQUISITION, ArtifactType.ACQUISITION)
    #     )
    #     if not acquisition_collection:
    #         raise ValueError(f"Acquisition {acquisition_name} has acquisition artifact collection")

    acquisition_path = (settings.ACQUISITION_DIR / acquisition_name).resolve()
    if not acquisition_path.is_relative_to(settings.ACQUISITION_DIR.resolve()):
        raise ValueError(
            f"Path {acquisition_path} is not within {settings.ACQUISITION_DIR}. Are you tryna path-traverse me, bro?"
        )
    elif not acquisition_path.exists():
        raise FileNotFoundError(f"Experiment {acquisition_path} does not exist")

    verify_acquisition_dir(acquisition_path)

    results = await asyncio.gather(
        sync(acquisition_path, settings.ANALYSIS_DIR),
        archive(acquisition_path, settings.ARCHIVE_DIR),
        return_exceptions=True,
    )

    if any(errors := [result for result in results if isinstance(result, Exception)]):
        raise AggregateError(*errors)

    rmtree(acquisition_path)

    # TODO: create acquisition collections as platereads complete
    # with get_db() as session:
    #     crud.create_artifact_collection_replica(
    #         session=session,
    #         artifact_collection=acquisition_collection,
    #         location=Repository.ARCHIVE,
    #     )
    #     crud.create_artifact_collection_replica(
    #         session=session,
    #         artifact_collection=acquisition_collection,
    #         location=Repository.ACQUISITION,
    #     )
    #     session.delete(acquisition_collection)

    # submit analysis tasks


@flow
async def post_plateread_handler(resource_id: str, before: str):
    if not (match := re.match(PLATEREAD_RESOURCE_REGEX, resource_id)):
        raise ValueError(f"Invalid plateread resource id: {resource_id}")

    plateread_id = int(match.group("plateread_id"))
    before = ProcessStatus(before)

    with get_db() as session:
        if not (plateread := session.get(PlatereadSpec, plateread_id)):
            raise ValueError(f"Plateread {plateread_id} not found")

        acquisition_name = plateread.acquisition_plan.acquisition.name

    match (before, plateread.status):
        case (ProcessStatus.RUNNING, ProcessStatus.COMPLETED):
            if all(
                spec.status == ProcessStatus.COMPLETED
                for spec in plateread.acquisition_plan.schedule
            ):
                await handle_post_acquisition(acquisition_name)
