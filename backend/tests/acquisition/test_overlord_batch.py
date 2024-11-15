import datetime
from pathlib import Path

from app.acquisition.overlord_batch import Batch

example_batch = Path(__file__).parent / "example_overlord_batch.xml"


def test_overlord_batch_from_xml():
    with example_batch.open("rb") as f:
        Batch.from_xml(f.read())


def test_overlord_batch_to_xml():
    with example_batch.open("rb") as f:
        batch = Batch.from_xml(f.read())
        batch.to_xml()


def tets_overlord_batch_from_python():
    Batch(
        start_after=datetime.datetime.now(), batch_name="foo", parent_batch_name="foo"
    )
