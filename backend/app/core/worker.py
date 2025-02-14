from prefect import serve

from app.acquisition.flows import get_deployments as get_acquisition_deployments
from app.gsheet_integration.flows import get_deployments as get_gsheet_deployments
from app.scheduler.flows import get_deployments as get_scheduler_deployments

"""
Hosts flows alongside the prefect API server.
"""


def run():
    serve(
        *get_gsheet_deployments(),
        *get_scheduler_deployments(),
        *get_acquisition_deployments(),
        print_starting_message=True,
    )
