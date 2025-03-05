from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from typer import Typer

from app.acquisition.flows.overlord import BatchParams, write_batch_xml
from app.acquisition.models import Location

app = Typer()


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


@app.command()
def dump_xmls(csv_path: Path, output_dir: Path = Path(".")):
    df = pd.read_csv(csv_path).fillna("")
    for _, row in df.iterrows():
        for params in _parse_batch_params(row, output_dir):
            write_batch_xml(params)


@app.command(hidden=True)
def dummy():
    print(":D")
