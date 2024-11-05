from datetime import timedelta

from sqlmodel import Session

from app.acquisition.crud import create_acquisition_plan
from app.acquisition.models import (
    AcquisitionPlanCreate,
    ImagingPriority,
)
from app.labware.models import Location
from tests.labware.utils import create_random_wellplate
from tests.utils import random_lower_string


def create_random_acquisition_plan(
    *, session: Session, wellplate_id: int | None = None, **kwargs
):
    if wellplate_id is None:
        wellplate = create_random_wellplate(session=session)
        wellplate_id = int(wellplate.id)

    kwargs.setdefault("name", random_lower_string())
    kwargs.setdefault("wellplate_id", wellplate_id)
    kwargs.setdefault("storage_location", Location.CQ1)
    kwargs.setdefault("protocol_name", random_lower_string())
    kwargs.setdefault("n_reads", 1)
    kwargs.setdefault("interval", timedelta(minutes=1))
    kwargs.setdefault("deadline_delta", timedelta(minutes=1))
    kwargs.setdefault("priority", ImagingPriority.NORMAL)

    acquisition_plan = AcquisitionPlanCreate(
        name=kwargs["name"],
        wellplate_id=kwargs["wellplate_id"],
        storage_location=kwargs["storage_location"],
        protocol_name=kwargs["protocol_name"],
        n_reads=kwargs["n_reads"],
        interval=kwargs["interval"],
        deadline_delta=kwargs["deadline_delta"],
        priority=kwargs["priority"],
    )
    return create_acquisition_plan(session=session, plan_create=acquisition_plan)
