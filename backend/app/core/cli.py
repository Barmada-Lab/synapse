from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from globus_compute_sdk import Executor
from typer import Typer

from app.acquisition.flows.analysis import submit_sbatch_job
from app.acquisition.flows.artifact_collections import _sync_cmd
from app.acquisition.flows.overlord import BatchParams, write_batch_xml
from app.acquisition.models import Location
from app.core.config import settings
from app.labware.flows import print_wellplate_barcode

app = Typer()


@app.command(
    help=(
        "Print wellplate barcodes given a CSV file conforming to the "
        "create_acquisition_plan format"
    )
)
def print_barcodes(csv_path: Path):
    df = pd.read_csv(csv_path).fillna("")
    for _, row in df.iterrows():
        print_wellplate_barcode(row["wellplate_name"])


def _parse_batch_params(
    row: pd.Series, kiosk_path: Path
) -> Generator[BatchParams, None, None]:
    acquisition_name = row["acquisition_name"]
    wellplate_name = row["wellplate_name"]
    storage_location = Location(row["storage_location"])
    storage_position = (
        int(row["storage_position"]) if row["storage_position"] != "" else None
    )
    n_reads = int(row["n_reads"])
    start_after = (
        datetime.fromisoformat(row["start_after"])
        if row["start_after"] != ""
        else datetime.now()
    )
    interval_mins = int(row["interval_mins"])
    interval = timedelta(minutes=interval_mins)
    protocol_name = row["protocol_name"]

    for read_idx in range(n_reads):
        yield BatchParams(
            storage_location=storage_location,
            read_idx=read_idx,
            created=start_after,
            start_after=start_after + read_idx * interval,
            interval=interval,
            acquisition_name=acquisition_name,
            wellplate_name=wellplate_name,
            protocol_name=protocol_name,
            kiosk_path=kiosk_path,
            storage_position=storage_position,
            plateread_id=None,
        )


@app.command(
    help=(
        "Dump Overlord XML files given a CSV conforming to the "
        "create_acquisition_plan format"
    )
)
def dump_xmls(csv_path: Path, output_dir: Path = Path(".")):
    df = pd.read_csv(csv_path).fillna("")
    for _, row in df.iterrows():
        for params in _parse_batch_params(row, output_dir):
            write_batch_xml(params)


@app.command(
    help=(
        "Sync acquisitions to the configured ANALYSIS_DIR, given a CSV file "
        "conforming to the create_analysis_plan format"
    )
)
def sync_acquisitions(csv_path: Path):
    df = pd.read_csv(csv_path).fillna("")
    orig = settings.ACQUISITION_DIR
    dest = settings.ANALYSIS_DIR
    for _, row in df.iterrows():
        acquisition_name = row["acquisition_name"]
        if not (orig / acquisition_name).exists():
            print(f"Acquisition {acquisition_name} not found")
            continue
        print(f"Syncing {acquisition_name} to {dest}")
        _sync_cmd(orig / acquisition_name, dest)


@app.command(
    help=(
        "Run analyses on the cluster given a CSV file conforming to the "
        "create_analysis_plan format. Requires the experiment to be present in "
        "ANALYSIS_DIR first."
    )
)
def run_analyses(csv_path: Path):
    df = pd.read_csv(csv_path).fillna("")
    with Executor(endpoint_id=settings.GLOBUS_ENDPOINT_ID) as executor:
        for _, row in df.iterrows():
            sbatch_args = [row["analysis_cmd"], *row["analysis_args"].split(",")]
            print(f"Submitting {sbatch_args} to the cluster")
            submit_sbatch_job(sbatch_args, executor)


@app.command(
    help=("Syncs and analyzes each row in a create_analysis_plan-formatted CSV file")
)
def sync_and_analyze(csv_path: Path):
    df = pd.read_csv(csv_path).fillna("")
    orig = settings.ACQUISITION_DIR
    dest = settings.ANALYSIS_DIR
    for _, row in df.iterrows():
        acquisition_name = row["acquisition_name"]
        if not (orig / acquisition_name).exists():
            print(f"Acquisition {acquisition_name} not found")
            continue
        print(f"Syncing {acquisition_name} to {dest}")
        _sync_cmd(orig / acquisition_name, dest)

        with Executor(endpoint_id=settings.GLOBUS_ENDPOINT_ID) as executor:
            sbatch_args = [row["analysis_cmd"], *row["analysis_args"].split(",")]
            print(f"Submitting {sbatch_args} to the cluster")
            submit_sbatch_job(sbatch_args, executor)


@app.command(hidden=True)
def dummy():
    print(":D")
