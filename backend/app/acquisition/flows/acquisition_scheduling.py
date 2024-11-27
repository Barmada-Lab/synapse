import logging
import re
from pathlib import Path
from xml.etree.ElementTree import canonicalize

from prefect import flow, task

from app.acquisition import crud as acquisition_crud
from app.acquisition.batch_model import (
    OVERLORD_STRFMT,
    Batch,
    Labware,
    LabwareCollection,
    OverlordBatchParams,
    ReadTime,
    ReadTimeCollection,
)
from app.acquisition.models import AcquisitionPlan, Location
from app.common.dt import local_now
from app.core.config import settings
from app.core.deps import get_db
from app.labware import crud as labware_crud
from app.labware.events import WELLPLATE_RESOURCE_REGEX

logger = logging.getLogger(__name__)


@task
def write_batches(plan: AcquisitionPlan, kiosk_path: Path):
    for i, spec in enumerate(plan.schedule, start=1):
        storage_location_map = {
            Location.CYTOMAT2: "C2",
            Location.HOTEL: "Plate Hotel",
        }
        storage_loc = storage_location_map[plan.storage_location]

        now_str = local_now().strftime(OVERLORD_STRFMT)
        match plan.storage_location:
            case Location.CYTOMAT2:
                xml_prefix = "CQ1 With Live Cells "  # yes, the space is intentional....
                storage_loc = "C2"
                run_mode = 1
            case Location.HOTEL:
                xml_prefix = "Run Mode 2"
                storage_loc = "Plate Hotel"
                run_mode = 2
            case _:
                raise ValueError(
                    f"Invalid plate storage location: {plan.storage_location}"
                )

        # we use the user_name param to achieve unique batch names.
        # it needs an underscore at the end for some reason.
        # the corresponding xml field must be populated with the same value.
        user_name = f"{plan.acquisition.name}_"
        parent_name = f"{xml_prefix}_{user_name}_{now_str}"
        batch_name = f"{parent_name}_READ{i:03d}"
        batch_path = kiosk_path / f"{batch_name}.xml"

        batch = Batch(
            start_after=spec.start_after,
            batch_name=batch_name,
            user=user_name,
            parent_batch_name=parent_name,
            run_mode=run_mode,
            read_times=ReadTimeCollection(
                items=[
                    ReadTime(
                        index=i,
                        interval=int(plan.interval.total_seconds() / 60),
                        value=spec.start_after,
                    )
                ]
            ),
            labware=LabwareCollection(
                items=[
                    Labware(
                        index=1,
                        type="96",
                        barcode=plan.wellplate.name,
                        start_location=storage_loc,
                        end_location=storage_loc,
                    )
                ]
            ),
            parameters=OverlordBatchParams(
                wellplate_barcode=plan.wellplate.name,
                plateread_id=spec.id,  # type: ignore
                acquisition_name=plan.acquisition.name,
                labware_type="96",
                plate_location_start=storage_loc,
                scans_per_plate=1,
                scan_time_interval=int(plan.interval.total_seconds()),
                cq1_protocol_name=plan.protocol_name,
                read_barcodes=True,
                plate_estimated_time=1337,
            ).to_parameter_collection(),
        )

        with open(batch_path, "w") as f:
            canonicalize(batch.to_xml(), out=f)


@flow
def check_to_schedule_acquisition(resource_id: str):
    if (match := re.match(WELLPLATE_RESOURCE_REGEX, resource_id)) is None:
        raise ValueError(f"Invalid wellplate resource id: {resource_id}")

    wellplate_name = match.group("wellplate_name")
    with get_db() as session:
        wellplate = labware_crud.get_wellplate_by_name(
            session=session, name=wellplate_name
        )

        if wellplate is None:
            raise ValueError(f"Wellplate {wellplate_name} not found")

        kiosk_path = settings.OVERLORD_DIR / "Batches" / "Kiosk"
        for plan in wellplate.acquisition_plans:
            if plan.storage_location == wellplate.location and plan.schedule == []:
                plan = acquisition_crud.schedule_plan(session=session, plan=plan)
                write_batches(plan, kiosk_path)
