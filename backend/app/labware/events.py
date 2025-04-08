from app.acquisition.flows.acquisition_planning import (
    check_to_schedule_acquisition_plan,
)

from .models import Location


def handle_wellplate_location_update(
    *, wellplate_id: int, origin: Location, dest: Location
) -> None:
    if origin == dest:
        return

    match (origin, dest):
        case (Location.EXTERNAL, Location.CYTOMAT2):
            # check to schedule
            check_to_schedule_acquisition_plan(wellplate_id=wellplate_id)

        case (Location.EXTERNAL, Location.HOTEL):
            # check to schedule
            check_to_schedule_acquisition_plan(wellplate_id=wellplate_id)
