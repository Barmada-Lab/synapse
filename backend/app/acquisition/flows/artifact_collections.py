import logging
import os
import platform
import shutil
from pathlib import Path

from prefect import get_run_logger, task
from prefect.cache_policies import NONE
from pydantic import DirectoryPath
from sqlmodel import Session

from app.acquisition import crud
from app.acquisition.consts import TAR_ZST_EXTENSION
from app.acquisition.models import (
    ArtifactCollection,
    Repository,
)
from app.common.proc import run_subprocess

logger = logging.getLogger(__name__)

TempPath = Path


def _sync_cmd(origin: DirectoryPath, dest_base: DirectoryPath) -> DirectoryPath:
    run_subprocess(["rsync", "-r", origin.as_posix(), dest_base.as_posix()]).unwrap()
    result_path = dest_base / origin.name

    if not result_path.exists():
        raise FileNotFoundError(f"Failed to sync {origin} to {dest_base}")
    return result_path


def _archive_cmd(origin: DirectoryPath, dest_base: DirectoryPath) -> Path:
    dest = dest_base / (origin.name + TAR_ZST_EXTENSION)
    match platform.system():
        case "Linux":
            run_subprocess(
                [
                    "tar",
                    "-c",
                    "-I",
                    "zstd -T4",
                    "-f",
                    dest.as_posix(),
                    "-C",
                    origin.parent.as_posix(),
                    origin.name,
                ]
            ).unwrap()
        case "Darwin":
            run_subprocess(
                [
                    "tar",
                    "-c",
                    "--zstd",
                    "--options",
                    "zstd:compression-level=4",
                    "-f",
                    dest.as_posix(),
                    "-C",
                    origin.parent.as_posix(),
                    origin.name,
                ]
            ).unwrap()
    if not dest.exists():
        raise FileNotFoundError(f"Failed to archive {origin} to {dest_base}")
    return dest


def _retrieve_cmd(origin: Path, dest_base: DirectoryPath) -> DirectoryPath:
    dest = dest_base / origin.name.replace(TAR_ZST_EXTENSION, "")
    match platform.system():
        case "Linux":
            run_subprocess(
                [
                    "tar",
                    "-x",
                    "-I",
                    "zstd",
                    "-f",
                    origin.as_posix(),
                    "-C",
                    dest_base.as_posix(),
                ]
            ).unwrap()
        case "Darwin":
            run_subprocess(
                [
                    "tar",
                    "-x",
                    "--zstd",
                    "-f",
                    origin.as_posix(),
                    "-C",
                    dest_base.as_posix(),
                ]
            ).unwrap()

    if not dest.exists():
        raise FileNotFoundError(f"Failed to archive {origin} to {dest_base}")
    return dest


@task(cache_policy=NONE)  # type: ignore[arg-type]
def _get_dest_path(collection: ArtifactCollection, dest: Repository) -> DirectoryPath:
    relpath = collection.acquisition_dir.relative_to(collection.location.path)
    return dest.path / relpath


@task(cache_policy=NONE)  # type: ignore[arg-type]
def _retrieve(collection: ArtifactCollection, dest: Repository):
    logger = get_run_logger()
    logger.info(f"Retrieving archived {collection} to {dest}")
    dest_path = _get_dest_path(collection, dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    _retrieve_cmd(collection.path, dest_path)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def _archive(collection: ArtifactCollection, dest: Repository):
    logger = get_run_logger()
    logger.info(f"Archiving {collection} to {dest}")
    dest_path = _get_dest_path(collection, dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    _archive_cmd(collection.path, dest_path)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def _sync(collection: ArtifactCollection, dest: Repository):
    logger = get_run_logger()
    logger.info(f"Syncing {collection} to {dest}")
    dest_path = _get_dest_path(collection, dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    _sync_cmd(collection.path, dest_path)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def copy_collection(
    *, collection: ArtifactCollection, dest: Repository, session: Session
) -> ArtifactCollection:
    match (collection.location, dest):
        case (Repository.ARCHIVE_STORE, _):
            _retrieve(collection, dest)
        case (_, Repository.ARCHIVE_STORE):
            _archive(collection, dest)
        case (_origin, _dest):
            if _origin == _dest:
                raise ValueError("Cannot copy to the same location")
            _sync(collection, dest)

    if not (
        new_collection := crud.get_artifact_collection_by_key(
            session=session,
            acquisition_id=collection.acquisition_id,
            key=(dest, collection.artifact_type),
        )
    ):
        new_collection = crud.create_artifact_collection_copy(
            session=session,
            artifact_collection=collection,
            location=dest,
        )
    return new_collection


def _cleanup_cmd(path: Path):
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            os.remove(path)
    except Exception as e:
        raise e


@task(cache_policy=NONE)  # type: ignore[arg-type]
def cleanup(collection: ArtifactCollection, session: Session):
    _cleanup_cmd(collection.path)
    session.delete(collection)
    session.commit()


@task(cache_policy=NONE)  # type: ignore[arg-type]
def move_collection(
    *, collection: ArtifactCollection, dest: Repository, session: Session
) -> ArtifactCollection:
    new_collection = copy_collection(collection=collection, dest=dest, session=session)
    cleanup(collection, session)
    return new_collection
