import asyncio
import logging
import os
import platform
import shutil
from pathlib import Path

from prefect import flow, task
from pydantic import DirectoryPath

from app.common.errors import AggregateError
from app.common.proc import run_subproc_async
from app.core.config import settings

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
def verify_experiment_dir(_local_dir: Path):
    # TODO
    pass


@flow
async def post_acquisition_flow(experiment_id: str):
    experiment_path = (settings.ACQUISITION_DIR / experiment_id).resolve()
    if not experiment_path.is_relative_to(settings.ACQUISITION_DIR.resolve()):
        raise ValueError(
            f"Path {experiment_path} is not within {settings.ACQUISITION_DIR}. Are you tryna path-traverse me, bro?"
        )

    elif not experiment_path.exists():
        raise FileNotFoundError(f"Experiment {experiment_path} does not exist")

    verify_experiment_dir(experiment_path)

    results = await asyncio.gather(
        sync(experiment_path, settings.ANALYSIS_DIR),
        archive(experiment_path, settings.ARCHIVE_DIR),
        return_exceptions=True,
    )
    if any(errors := [result for result in results if isinstance(result, Exception)]):
        raise AggregateError(*errors)

    rmtree(experiment_path)


def get_deployments():
    return [
        post_acquisition_flow.to_deployment(name="post-acquisition-flow"),
    ]
