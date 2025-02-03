from prefect import serve

from app.gsheet_integration.flows import get_deployments as get_gsheet_deployments

"""
Hosts flows alongside the prefect API server.
"""


def run():
    serve(
        *get_gsheet_deployments(),
        print_starting_message=True,
    )
