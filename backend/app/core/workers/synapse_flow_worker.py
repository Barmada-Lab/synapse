from prefect import serve

from app.acquisition.flows import get_deployments as get_acquisition_deployments

"""
Hosts flows alongside the prefect API server.
"""


def run():
    serve(
        *get_acquisition_deployments(),
        print_starting_message=True,
    )
