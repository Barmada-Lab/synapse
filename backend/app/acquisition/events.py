import re

from prefect.events import emit_event

from .models import PlatereadSpec, PlatereadStatus

PLATEREAD_RESOURCE_REGEX = r"^plateread\.(?P<plateread_id>\w+)$"


def emit_plateread_status_update(*, plateread: PlatereadSpec, before: PlatereadStatus):
    if plateread.status == before:
        return

    plan_name = plateread.acquisition_plan.name
    resource_id = f"plateread.{plateread.id}"
    if not re.match(PLATEREAD_RESOURCE_REGEX, resource_id):
        raise ValueError(f"Invalid plateread id: {plateread.id}")

    plateread_resource = {
        "prefect.resource.id": resource_id,
        "status.before": before.value,
        "status.after": plateread.status.value,
    }
    acquisition_plan_resource = {
        "prefect.resource.id": f"acquisition_plan.{plan_name}",
        "prefect.resource.role": "automation",
    }
    emit_event(
        "plateread.status_update",
        resource=plateread_resource,
        related=[acquisition_plan_resource],
    )
