from pathlib import Path

from app.acquisition.overlord_batch import Batch

example_batch = Path(__file__).parent / "example_overlord_batch.xml"


def test_overlord_batch_from_xml():
    with example_batch.open("rb") as f:
        Batch.from_xml(f.read())
