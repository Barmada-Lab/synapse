from app.acquisition.flows.acquisition import on_plateread_completed
from app.acquisition.models import (
    ProcessStatus,
)


def handle_plateread_status_update(plateread_id: int, status: ProcessStatus) -> None:
    match status:
        case ProcessStatus.COMPLETED:
            on_plateread_completed(plateread_id)  # type: ignore[arg-type]
        case _:
            pass
