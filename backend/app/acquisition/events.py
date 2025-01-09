from fastapi import BackgroundTasks
from fastapi_events.handlers.local import local_handler
from fastapi_events.typing import Event
from pydantic import BaseModel

from app.acquisition.flows.acquisition import on_plateread_completed
from app.acquisition.models import Location, ProcessStatus, SlurmJobStatus


class PlatereadStatusUpdate(BaseModel):
    __event_name__ = "plateread-status-update"
    plateread_id: int
    status: ProcessStatus


class AnalysisStatusUpdate(BaseModel):
    __event_name__ = "analysis-status-update"
    analysis_id: int
    status: SlurmJobStatus


class WellplateLocationUpdate(BaseModel):
    __event_name__ = "wellplate-location-update"
    wellplate_id: int
    location: Location


async def _on_plateread_completed_wrapper(plateread_id: int):
    await on_plateread_completed(plateread_id)


@local_handler.register(event_name=PlatereadStatusUpdate.__event_name__)
async def on_plateread_status_update(_event: Event, background_tasks: BackgroundTasks):
    event = PlatereadStatusUpdate.model_validate(_event[1])

    match event.status:
        case ProcessStatus.COMPLETED:
            background_tasks.add_task(
                _on_plateread_completed_wrapper, event.plateread_id
            )
        case _:
            pass
