import logging
from pathlib import Path

import tifffile
from prefect import flow, task
from tifffile import COMPRESSION, TiffFile

from app.acquisition import crud
from app.acquisition.flows.analysis import handle_analyses
from app.acquisition.flows.artifact_collections import (
    copy_collection,
    move_collection,
)
from app.acquisition.flows.fiftyone import ingest_acquisition_data
from app.acquisition.models import (
    ArtifactCollectionCreate,
    ArtifactType,
    PlatereadSpec,
    Repository,
)
from app.core.config import settings
from app.core.deps import get_db

logger = logging.getLogger(__name__)


@task
def compress_cq1_acquisition(acquisition_data_path: Path):
    """
    Compress all uncompressed .tif files in the provided acquisition_data directory

    (assumes standard CQ1 directory structure)

    Args:
        acquisition_data_path - path to the acquisition's acquisition_data directory
    """
    pattern = "*/Projection/*[!.tmp].tif"
    for file in acquisition_data_path.glob(pattern):
        with TiffFile(file) as tif:
            is_compressed = tif.pages[0].compression != COMPRESSION.NONE
            if is_compressed:
                continue
            data = tif.asarray()

        # write to a temporary file to allow for atomic replacement
        tmp_file = file.with_suffix(".tmp.tif")
        tifffile.imwrite(tmp_file, data, compression=COMPRESSION.ZSTD)
        tmp_file.replace(file)


@flow
def on_plateread_completed(plateread_id: int):
    with get_db() as session:
        if not (plateread := session.get(PlatereadSpec, plateread_id)):
            raise ValueError(f"Plateread {plateread_id} not found")
        elif not plateread.acquisition_plan:
            raise ValueError(f"Plateread {plateread_id} has no acquisition plan")

        acquisition = plateread.acquisition_plan.acquisition

        # Check for new acquisition data
        acquisition_collection = acquisition.get_collection(
            ArtifactType.ACQUISITION_DATA, Repository.ACQUISITION_STORE
        )
        if not acquisition_collection:
            acquisition_collection = crud.create_artifact_collection(
                session=session,
                artifact_collection_create=ArtifactCollectionCreate(
                    location=Repository.ACQUISITION_STORE,
                    artifact_type=ArtifactType.ACQUISITION_DATA,
                    acquisition_id=acquisition.id,  # type: ignore[arg-type]
                ),
            )

        compress_cq1_acquisition(acquisition_collection.path)

        if settings.CREATE_FIFTYONE_DATASETS:
            ingest_acquisition_data(acquisition.name, acquisition_collection.path)

        copy_collection(
            collection=acquisition_collection,
            dest=Repository.ANALYSIS_STORE,
            session=session,
        )

        handle_analyses(acquisition, session)

        n_endstates = sum(
            read.status.is_endstate for read in plateread.acquisition_plan.reads
        )
        total_reads = plateread.acquisition_plan.n_reads
        if n_endstates == total_reads:
            # archive acquisition data
            move_collection(
                collection=acquisition_collection,
                dest=Repository.ARCHIVE_STORE,
                session=session,
            )
