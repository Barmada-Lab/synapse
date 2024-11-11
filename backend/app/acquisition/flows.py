import asyncio
import logging
import os
import platform
import re
import shutil
from pathlib import Path

from prefect import flow, task
from prefect.events import DeploymentEventTrigger
from pydantic import DirectoryPath

from app.common.errors import AggregateError
from app.common.proc import run_subproc_async
from app.core.config import settings
from app.core.deps import get_db
from app.labware import crud as labware_crud
from app.labware.utils import WELLPLATE_RESOURCE_REGEX

from . import crud as acquisition_crud
from .models import Location

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


@flow
def check_to_schedule_acquisition(resource_id: str):
    if (match := re.match(WELLPLATE_RESOURCE_REGEX, resource_id)) is None:
        raise ValueError(f"Invalid wellplate resource id: {resource_id}")

    wellplate_name = match.group("wellplate_name")
    with get_db() as session:
        wellplate = labware_crud.get_wellplate_by_name(
            session=session, name=wellplate_name
        )

        if wellplate is None:
            raise ValueError(f"Wellplate {wellplate_name} not found")

        for plan in wellplate.acquisition_plans:
            if plan.storage_location == wellplate.location and plan.schedule == []:
                acquisition_crud.schedule_plan(session=session, plan=plan)
                # dump overlord xmls


def get_deployments():
    return [
        post_acquisition_flow.to_deployment(name="post-acquisition-flow"),
        check_to_schedule_acquisition.to_deployment(
            name="schedule-acquisition",
            triggers=[
                DeploymentEventTrigger(
                    event="wellplate.location_update",
                    match={
                        "prefect.resource.id": "wellplate.*",
                        "location.before": Location.EXTERNAL.value,
                        "location.after": [
                            Location.CYTOMAT2.value,
                            Location.HOTEL.value,
                        ],
                    },
                    parameters={"resource_id": "{{ event.resource.id }}"},
                    name="schedule-new-plate",
                )
            ],
        ),
    ]
