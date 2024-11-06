# import logging

from prefect import serve

from app.acquisition.flows import get_deployments as get_acquisition_deployments
from app.labware.flows import get_deployments as get_labware_deployments


def run():
    serve(
        *get_acquisition_deployments(),
        *get_labware_deployments(),
        print_starting_message=True,
    )
