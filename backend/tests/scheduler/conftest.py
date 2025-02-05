import pytest
from prefect.testing.utilities import prefect_test_harness
from sqlmodel import Session, select

from app.acquisition.models import Acquisition


@pytest.fixture(autouse=True, scope="module")
def prefect_test_fixture():
    with prefect_test_harness():
        yield


@pytest.fixture(autouse=True, scope="function")
def serial_cleanup(db: Session, serial):
    yield serial
    specs = db.exec(select(Acquisition)).all()
    for spec in specs:
        db.delete(spec)
    db.commit()
