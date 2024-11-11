import re

from prefect.events import emit_event

from .models import Location, Wellplate

WELLPLATE_RESOURCE_REGEX = r"^wellplate\.(?P<wellplate_name>\w+)$"

def emit_wellplate_location_update(*, wellplate: Wellplate, before: Location) -> None:
    if wellplate.location == before:
        return

    wellplate_name = wellplate.name
    resource_id = f"wellplate.{wellplate_name}"
    if not re.match(WELLPLATE_RESOURCE_REGEX, resource_id):
        raise ValueError(f"Invalid wellplate name: {wellplate_name}")

    wellplate_resource = {
        "prefect.resource.id": resource_id,
        "location.before": before.value,
        "location.after": wellplate.location.value,
    }

    emit_event("wellplate.location_update", resource=wellplate_resource)
