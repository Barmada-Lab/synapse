from prefect.task_worker import serve

from app.labware.flows import get_tasks

"""
Hosts tasks alongside the prefect server. Used primarily for work queueing.
"""


def run():
    serve(
        *get_tasks(),
    )
