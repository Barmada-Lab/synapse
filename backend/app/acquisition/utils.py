from prefect.events import emit_event

from .models import PlatereadSpec, PlatereadStatus


def emit_plateread_status_update(*, plateread: PlatereadSpec, before: PlatereadStatus):
    if plateread.status == before:
        return
    plan_name = plateread.acquisition_plan.name
    start_after_str = plateread.start_after.isoformat()
    plateread_resource = {
        "prefect.resource.id": f"acquisition_plan.{plan_name}.{start_after_str}",
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
