import logging

from prefect import flow

from app.acquisition import crud
from app.acquisition.flows.analysis import handle_analyses
from app.acquisition.flows.artifact_collections import (
    copy_collection,
    move_collection,
    update_collection_artifacts,
)
from app.acquisition.models import (
    ArtifactCollectionCreate,
    ArtifactType,
    PlatereadSpec,
    Repository,
)
from app.core.deps import get_db

logger = logging.getLogger(__name__)


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

        update_collection_artifacts(collection=acquisition_collection, session=session)
        copy_collection(
            collection=acquisition_collection,
            dest=Repository.ANALYSIS_STORE,
            session=session,
        )

        handle_analyses(acquisition, session)

        n_endstates = sum(
            read.status.is_endstate for read in plateread.acquisition_plan.schedule
        )
        total_reads = plateread.acquisition_plan.n_reads
        if n_endstates == total_reads:
            # archive acquisition data
            move_collection(
                collection=acquisition_collection,
                dest=Repository.ARCHIVE_STORE,
                session=session,
            )
