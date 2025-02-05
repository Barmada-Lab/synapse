import logging

from prefect import flow

from app.acquisition import crud as acquisition_crud
from app.core.deps import get_db
from app.labware.models import Wellplate

logger = logging.getLogger(__name__)


@flow
def check_to_implement_plans(wellplate_id: int):
    with get_db() as session:
        wellplate = session.get(Wellplate, wellplate_id)
        if wellplate is None:
            raise ValueError(f"Wellplate {wellplate_id} not found")

        for plan in wellplate.acquisition_plans:
            if plan.storage_location == wellplate.location and plan.reads == []:
                plan = acquisition_crud.implement_plan(session=session, plan=plan)
