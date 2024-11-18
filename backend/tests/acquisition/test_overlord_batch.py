import datetime
from pathlib import Path

from app.acquisition.batch_model import Batch

example_batch = Path(__file__).parent / "example_overlord_batch.xml"


def test_overlord_batch_from_python():
    Batch(
        start_after=datetime.datetime.now(), batch_name="foo", parent_batch_name="foo"
    )
