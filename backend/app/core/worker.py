from prefect import serve

from app.acquisitions.flows import post_acquisition_flow


def run():
    serve(
        post_acquisition_flow.to_deployment(name="post-acquisition-flow"),
    )
