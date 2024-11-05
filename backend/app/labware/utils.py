from prefect.events import emit_event

from .models import Location, Wellplate


def emit_wellplate_location_update(*, wellplate: Wellplate, before: Location) -> None:
    if wellplate.location == before:
        return

    wellplate_name = wellplate.name
    wellplate_resource = {
        "prefect.resource.id": f"wellplate.{wellplate_name}",
        "location.before": before.value,
        "location.after": wellplate.location.value,
    }

    emit_event("wellplate.location_update", resource=wellplate_resource)
