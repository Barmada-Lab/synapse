from prefect.events import DeploymentEventTrigger, ResourceSpecification

from app.labware.models import Location

from .acquisition_scheduling import check_to_schedule_acquisition


def get_deployments():
    return [
        check_to_schedule_acquisition.to_deployment(
            name="schedule-acquisition",
            triggers=[
                DeploymentEventTrigger(
                    expect={"wellplate.location_update"},
                    match=ResourceSpecification(
                        {
                            "prefect.resource.id": "wellplate.*",
                            "location.before": Location.EXTERNAL.value,
                            "location.after": [
                                Location.CYTOMAT2.value,
                                Location.HOTEL.value,
                            ],
                        }
                    ),
                    parameters={"resource_id": "{{ event.resource.id }}"},
                    name="schedule-new-plate",
                )
            ],
        ),
    ]
