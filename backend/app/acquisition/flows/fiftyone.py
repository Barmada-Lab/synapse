import logging
from pathlib import Path

import fiftyone as fo  # type: ignore
import pandas as pd
import tifffile
from acquisition_io.loaders.cq1_loader import get_experiment_df
from PIL import Image
from prefect import flow, task
from skimage import exposure

from app.core.config import settings

logger = logging.getLogger(__name__)


@task
def _get_or_create_dataset(name: str) -> fo.Dataset:
    media_dir = settings.FIFTYONE_DIR / name
    media_dir.mkdir(parents=True, exist_ok=True)

    if fo.dataset_exists(name):
        return fo.load_dataset(name)
    else:
        dataset = fo.Dataset(name=name)
        dataset.info["media_dir"] = str(media_dir)  # type: ignore
        dataset.persistent = True
        return dataset


@task
def _populate_dataset(dataset: fo.Dataset, df: pd.DataFrame):
    """Idempotently populate a FiftyOne dataset with samples derived from a provided acquisition dataframe."""
    axes = df.index.names
    media_dir = Path(dataset.info["media_dir"])  # type: ignore

    def prepare_sample(coords, row):
        raw_path = row["path"]
        fields_dict = dict(zip(axes, coords, strict=False))

        region = fields_dict["region"]
        field = fields_dict["field"]
        z = fields_dict["z"]
        time = fields_dict["time"]
        channel = fields_dict["channel"]

        filename = f"T{time}_C{channel}_R{region}_F{field}_Z{z}.png"
        png_path = media_dir / filename
        if png_path.exists():
            return None

        fields_dict["region_field_key"] = "-".join(map(str, [region, field, z]))
        fields_dict["time_stack_key"] = "-".join(map(str, [region, field, z, channel]))
        fields_dict["channel_stack_key"] = "-".join(
            map(
                str,
                [
                    region,
                    field,
                    z,
                    time,
                ],
            )
        )
        fields_dict["z_stack_key"] = "-".join(
            map(
                str,
                [
                    region,
                    field,
                    time,
                    channel,
                ],
            )
        )

        arr = tifffile.imread(raw_path)
        clahe = exposure.equalize_adapthist(arr)
        rescaled = exposure.rescale_intensity(clahe, out_range="uint8")
        image = Image.fromarray(rescaled)
        image.save(png_path, format="PNG")

        return (raw_path, png_path, fields_dict)

    for index, row in df.iterrows():
        result = prepare_sample(index, row)
        if result is None:
            continue
        raw_path, png_path, fields_dict = result
        sample = fo.Sample(filepath=png_path)
        sample["raw_path"] = str(raw_path)  # attach the rawpath for quantitative stuff
        for key, value in fields_dict.items():
            sample[key] = value
        dataset.add_sample(sample)

    if not dataset.has_saved_view("timeseries"):
        timeseries_view = dataset.group_by("time_stack_key", order_by="time")
        dataset.save_view("timeseries", timeseries_view)

    if not dataset.has_saved_view("channel_stacks"):
        channel_stack_view = dataset.group_by("channel_stack_key", order_by="channel")
        dataset.save_view("channel_stacks", channel_stack_view)

    if not dataset.has_saved_view("z_stacks"):
        z_stack_view = dataset.group_by("z_stack_key", order_by="z")
        dataset.save_view("z_stacks", z_stack_view)

    dataset.save()


@flow
def ingest_acquisition_data(acquisition_name: str, acq_data_path: Path):
    dataset = _get_or_create_dataset(acquisition_name)
    df = get_experiment_df(acq_data_path, ordinal_time=True).reset_index()
    df = df.set_index(["region", "field", "time", "channel", "z"])
    _populate_dataset(dataset, df)
