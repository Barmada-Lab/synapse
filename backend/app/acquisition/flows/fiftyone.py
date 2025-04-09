import logging
from pathlib import Path

import fiftyone as fo  # type: ignore
import numpy as np
import pandas as pd
import tifffile
import xarray as xr
from acquisition_io.loaders.cq1_loader import get_experiment_df
from acquisition_io.utils import iter_idx_prod
from PIL import Image
from prefect import flow, task
from skimage import exposure
from skimage.measure import regionprops

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
        dataset.info["media_dir"] = str(media_dir)
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
def ingest_acquisition_data(acquisition_name: str, acquisition_data_path: Path):
    """Ingest CQ1 acquisition data into a FiftyOne dataset.

    Args:
        acquisition_name - name of the dataset to populate
        acquisition_data_path - path to the acquisition's acquisition_data directory
    """
    dataset = _get_or_create_dataset(acquisition_name)
    df = get_experiment_df(acquisition_data_path, ordinal_time=True).reset_index()
    df = df.set_index(["region", "field", "time", "channel", "z"])
    _populate_dataset(dataset, df)


def _add_detection_results(
    sample: fo.Sample, labels: np.ndarray, preds: np.ndarray, live_label: int
):
    detections = []
    for props in regionprops(labels):
        mask = labels == props.label
        prediction = np.bincount(preds[mask]).argmax()
        pred_label = "live" if prediction == live_label else "dead"
        detection = fo.Detection.from_mask(mask, label=pred_label)
        detections.append(detection)
    sample["predictions"] = fo.Detections(detections=detections)
    return sample


def import_survival(dataset: fo.Dataset, survival_results: xr.Dataset):
    for frame in iter_idx_prod(survival_results, subarr_dims=["y", "x"]):
        selector: dict = {coord: frame[coord].values.tolist() for coord in frame.coords}
        # convert time to 0-indexed ints
        selector["time"] = int(
            np.where(frame["time"].values == survival_results["time"].values)[0][0]
        )
        preds = frame["preds"].values
        live_label = frame["preds"].attrs["live_label"]
        labels = frame["nuc_labels"].values
        for match in dataset.match(selector):
            _add_detection_results(match, labels, preds, live_label).save()

    dataset.app_config.color_scheme = fo.ColorScheme(
        color_pool=[
            "#7bc043",  # green
            "#ee4035",  # red
            "#f37736",  # orange
            "#0392cf",  # blue
        ],
        color_by="value",
        fields=[
            {
                "path": "ground_truth",
                "colorByAttribute": "label",
                "valueColors": [
                    {"value": "dead", "color": "#ee4035"},
                    {"value": "live", "color": "#7bc043"},
                ],
            },
            {
                "path": "predictions",
                "colorByAttribute": "label",
                "valueColors": [
                    {"value": "dead", "color": "#ee4035"},
                    {"value": "live", "color": "#7bc043"},
                ],
            },
            {
                "path": "predictions",
                "colorByAttribute": "eval",
                "valueColors": [
                    {"value": "fp", "color": "#0392cf"},
                    {"value": "fn", "color": "#f37736"},
                    {"value": "tp", "color": "#7bc043"},
                    {"value": "tn", "color": "#ee4035"},
                ],
            },
        ],
    )
    dataset.save()


@flow
def ingest_survival_results(acquisition_name: str, survival_results_path: Path):
    """Ingest Cytomancer survival results into a FiftyOne dataset.

    Args:
        acquisition_name - The name of the acquisition to ingest the survival results into.
        survival_results_path - path to the survival results zarr file
    """
    dataset = fo.load_dataset(acquisition_name)
    ds = xr.open_zarr(survival_results_path)
    import_survival(dataset, ds)


@task
def tag_dataset(dataset: fo.Dataset, map_df: pd.DataFrame):
    for idx, row in map_df.iterrows():
        for _match in dataset.match(fo.F("region") == idx):
            cleaned = row.dropna()
            if "cells" in cleaned:
                _match["cell_line"] = cleaned["cells"]
            treatments = []
            if "Treatment1" in cleaned:
                treatments.append(cleaned["Treatment1"])
            if "Treatment2" in cleaned:
                treatments.append(cleaned["Treatment2"])
            if "Treatment3" in cleaned:
                treatments.append(cleaned["Treatment3"])
            if "Treatment4" in cleaned:
                treatments.append(cleaned["Treatment4"])
            if any(treatments):
                _match["treatments"] = treatments
            _match.save()


@flow
def ingest_map_file(acquisition_name: str, map_path: Path):
    """Ingest a map file into a populated FiftyOne dataset.

    Args:
        acquisition_name - The name of the acquisition to ingest the map into.
        map_path - path to the map csv file
    """
    dataset = fo.load_dataset(acquisition_name)
    map_df = pd.read_csv(map_path, index_col="well")
    tag_dataset(dataset, map_df)
