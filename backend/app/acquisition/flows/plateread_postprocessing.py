import asyncio
import logging
import os
import platform
import re
import shutil
from pathlib import Path

from prefect import flow, task
from prefect.events import emit_event
from pydantic import DirectoryPath
from sqlmodel import Session
from synapse_greatlakes.messages import Message, RequestSubmitJob

from app.acquisition import crud
from app.acquisition.consts import TAR_ZST_EXTENSION
from app.acquisition.events import PLATEREAD_RESOURCE_REGEX
from app.acquisition.models import (
    AnalysisPlan,
    ArtifactCollection,
    ArtifactType,
    PlatereadSpec,
    ProcessStatus,
    Repository,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecUpdate,
    SlurmJobStatus,
    get_acquisition_path,
)
from app.common.errors import AggregateError
from app.common.proc import run_subproc_async
from app.core.deps import get_db

logger = logging.getLogger(__name__)


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


# call separated to allow mocking
async def _sync_cmd(origin: Path, dest: DirectoryPath):
    await run_subproc_async(f"rsync -r {origin} {dest}", check=True)


@task
async def sync(origin: Path, dest: DirectoryPath):
    await _sync_cmd(origin, dest)


# call separated to allow mocking
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
    dest_zst = dest / (origin.name + TAR_ZST_EXTENSION)
    await _archive_cmd(dest_zst, origin)


@task
async def sync_and_archive(session: Session, acquisition_artifacts: ArtifactCollection):
    acquisition_name = acquisition_artifacts.acquisition.name

    # setup destination paths
    analysis_acquisition_path = get_acquisition_path(
        Repository.ANALYSIS, acquisition_name
    )
    archive_acquisition_path = get_acquisition_path(
        Repository.ARCHIVE, acquisition_name
    )

    if not analysis_acquisition_path.exists():
        analysis_acquisition_path.mkdir()
    if not archive_acquisition_path.exists():
        archive_acquisition_path.mkdir()

    # TODO: fuse sync/archive with modifying db records
    results = await asyncio.gather(
        sync(acquisition_artifacts.path, analysis_acquisition_path),
        archive(acquisition_artifacts.path, archive_acquisition_path),
        return_exceptions=True,
    )

    if any(errors := [result for result in results if isinstance(result, Exception)]):
        raise AggregateError(*errors)

    session.add(acquisition_artifacts)

    crud.create_artifact_collection_replica(
        session=session,
        artifact_collection=acquisition_artifacts,
        location=Repository.ARCHIVE,
    )
    crud.create_artifact_collection_replica(
        session=session,
        artifact_collection=acquisition_artifacts,
        location=Repository.ANALYSIS,
    )
    session.delete(acquisition_artifacts)
    cleanup(acquisition_artifacts.path)


@task
def submit_analysis_request(analysis_spec: SBatchAnalysisSpec):
    event = Message(
        resource=f"sbatch_analysis.{analysis_spec.id}",
        payload=RequestSubmitJob(
            script=analysis_spec.analysis_cmd,
            args=analysis_spec.analysis_args,
        ),
    ).to_event()
    emit_event(**event.model_dump())


@task
def submit_analysis_plan(session: Session, analysis_plan: AnalysisPlan):
    for analysis_spec in analysis_plan.sbatch_analyses:
        if analysis_spec.status == SlurmJobStatus.UNSUBMITTED:
            submit_analysis_request(analysis_spec)
            crud.update_analysis_spec(
                session=session,
                db_analysis=analysis_spec,
                update=SBatchAnalysisSpecUpdate(status=SlurmJobStatus.SUBMITTED),
            )


@flow
def handle_submit_analysis_plan(acquisition_name: str):
    with get_db() as session:
        acquisition = crud.get_acquisition_by_name(
            session=session, name=acquisition_name
        )
        if not acquisition:
            raise ValueError(f"Acquisition {acquisition_name} not found")

        analysis_plan = acquisition.analysis_plan
        # **NOTE** only works for endpoint analysis- doesn't handle intermediate analyses
        if analysis_plan is not None:
            submit_analysis_plan(session, analysis_plan)


@flow
async def handle_post_acquisition(acquisition_name: str):
    with get_db() as session:
        acquisition = crud.get_acquisition_by_name(
            session=session, name=acquisition_name
        )
        if not acquisition:
            raise ValueError(f"Acquisition {acquisition_name} not found")

        acquisition_collection = crud.get_artifact_collection_by_key(
            session=session,
            acquisition_id=acquisition.id,  # type: ignore
            key=(Repository.ACQUISITION, ArtifactType.ACQUISITION),
        )
        if not acquisition_collection:
            raise ValueError(
                f"{acquisition_name} doesn't have an acquisition artifact collection"
            )
        elif not acquisition_collection.path.exists():
            raise FileNotFoundError(
                f"{acquisition_name} artifact collection not found at path {acquisition_collection.path}"
            )
        elif not acquisition_collection.path.is_dir():
            raise NotADirectoryError(
                f"{acquisition_name} artifact collection is not a directory: {acquisition_collection.path}"
            )

        await sync_and_archive(session, acquisition_collection)

    handle_submit_analysis_plan(acquisition_name)


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
