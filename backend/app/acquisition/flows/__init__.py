from prefect.events import DeploymentEventTrigger, ResourceSpecification

from app.labware.models import Location

from .acquisition_scheduling import check_to_schedule_acquisition
from .plateread_postprocessing import (
    handle_submit_analysis_plan,
    post_plateread_handler,
)


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
        post_plateread_handler.to_deployment(
            name="post-acquisition",
            triggers=[
                DeploymentEventTrigger(
                    expect={"acquisition.plateread_completed"},
                    match=ResourceSpecification(
                        {
                            "prefect.resource.id": "plateread.*",
                            "status.before": "*",
                        }
                    ),
                    parameters={
                        "plateread_id": "{{ event.resource.id }}",
                        "before": "{{ event.status.before }}",
                    },
                    name="post-acquisition",
                )
            ],
        ),
        handle_submit_analysis_plan.to_deployment("submit-analysis-plan"),
    ]
