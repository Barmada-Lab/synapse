import random
from collections import defaultdict

import pandas as pd

from app.core.config import settings

N = 50


def get_n(n_avg):
    """
    Random variable returning floor(n_avg) with probability 1 - remainder,
    and ceil(n_avg) with probability remainder, where remainder is
    n_avg - floor(n_avg).
    """
    n_low = int(n_avg)
    remainder = n_avg - n_low
    return random.choices([n_low, n_low + 1], weights=[1 - remainder, remainder])[0]


def main():
    cell_type_counts = defaultdict(int)
    for acquisition_dir in settings.ACQUISITION_DIR.glob("*"):
        if (
            not (acquisition_dir / "acquisition_data").exists()
            or not (acquisition_dir / "analysis" / "map.csv").exists()
            or not (acquisition_dir / "scrcatch" / "survival_processed.zarr").exists()
        ):
            continue

        map_df = pd.read_csv(acquisition_dir / "analysis" / "map.csv")
        for cell_type in map_df["cell_type"].dropna().unique():
            cell_type_counts[cell_type] += 1

    for acquisition_dir in settings.ACQUISITION_DIR.glob("*"):
        map_df = pd.read_csv(acquisition_dir / "analysis" / "map.csv")
        # exp_df = get_experiment_df(acquisition_dir, ordinal_time=True)
        for cell_type in map_df["cell_type"].dropna().unique():
            n = get_n(N / cell_type_counts[cell_type])
            wells = map_df[map_df["cell_type"] == cell_type]["well"].unique()
            sample_wells = random.sample(wells, n)
            print(n, sample_wells)
