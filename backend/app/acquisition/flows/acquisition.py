import logging

from prefect import flow

from app.acquisition.flows.analysis import handle_analyses
from app.acquisition.models import (
    PlatereadSpec,
)
from app.core.deps import get_db

logger = logging.getLogger(__name__)


@flow
async def on_plateread_completed(plateread_id: int):
    with get_db() as session:
        if not (plateread := session.get(PlatereadSpec, plateread_id)):
            raise ValueError(f"Plateread {plateread_id} not found")
        elif not plateread.acquisition_plan:
            raise ValueError(f"Plateread {plateread_id} has no acquisition plan")

        acquisition = plateread.acquisition_plan.acquisition
        await handle_analyses(acquisition, session)
