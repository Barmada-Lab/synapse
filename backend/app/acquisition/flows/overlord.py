from datetime import datetime
from typing import Annotated, Literal
from xml.etree.ElementTree import canonicalize

from prefect import task
from prefect.cache_policies import NONE
from pydantic import PlainSerializer
from pydantic.dataclasses import dataclass
from pydantic_xml import BaseXmlModel, attr, element
from sqlmodel import Session

from app.acquisition import crud
from app.acquisition.models import (
    Location,
    PlatereadSpec,
    PlatereadSpecUpdate,
    ProcessStatus,
)
from app.common.dt import local_now, to_local_tz
from app.core.config import settings

OVERLORD_STRFMT = "%Y-%m-%d_%H-%M-%S"


@task(cache_policy=NONE)
def submit_plateread_spec(*, session: Session, spec: PlatereadSpec):
    plan = spec.acquisition_plan
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
            raise ValueError(f"Invalid plate storage location: {plan.storage_location}")

    i = sorted(spec.acquisition_plan.reads, key=lambda x: x.deadline).index(spec) + 1

    # we use the user_name param to achieve unique batch names.
    # it needs an underscore at the end for some reason.
    # the corresponding xml field must be populated with the same value.
    user_name = f"{plan.acquisition.name}_"
    parent_name = f"{xml_prefix}_{user_name}_{now_str}"
    batch_name = f"{parent_name}_READ{i:03d}"
    batch_path = settings.OVERLORD_DIR / "Batches" / "Kiosk" / f"{batch_name}.xml"

    deadline = spec.deadline if spec.deadline else datetime(9999, 12, 31, 23, 59, 59)

    start_after = datetime.now()
    batch = Batch(
        start_after=start_after,
        batch_name=batch_name,
        user=user_name,
        parent_batch_name=parent_name,
        run_mode=run_mode,
        read_times=ReadTimeCollection(
            items=[
                ReadTime(
                    index=i,
                    interval=int(plan.interval.total_seconds() / 60),
                    value=start_after,
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
            wellplate_storage_position=plan.storage_position
            if plan.storage_position is not None
            else -1,
            plateread_id=spec.id,  # type: ignore
            acquisition_name=plan.acquisition.name,
            labware_type="96",
            plate_location_start=storage_loc,
            scans_per_plate=1,
            scan_time_interval=int(plan.interval.total_seconds()),
            cq1_protocol_name=plan.protocol_name,
            plate_estimated_time=1337,
            deadline=deadline,
        ).to_parameter_collection(),
    )

    with open(batch_path, "w") as f:
        canonicalize(batch.to_xml(), out=f)

    crud.update_plateread(
        session=session,
        db_plateread=spec,
        plateread_in=PlatereadSpecUpdate(status=ProcessStatus.SCHEDULED),
    )

    return batch_path


class OverlordParameter(BaseXmlModel):
    name: str = element(tag="Name")
    type: Literal["Text"] | Literal["Numeric"] | Literal["TrueFalse"] = element(
        tag="Type"
    )
    value: str | None = element(tag="Value", default=None)
    include_in_summary: bool = element(tag="IncludeInSummary", default=True)


class ReadTime(BaseXmlModel):
    index: int = attr()
    interval: int = element(tag="Interval")
    value: "OtherOverlordDatetime" = element(tag="Value")


class Labware(BaseXmlModel):
    index: int = attr()
    type: str = attr()
    barcode: str | None = attr()
    start_location: str = attr(name="startLocation")
    end_location: str = attr(name="endLocation")
    random_access_position: int = attr(name="randomAccessPosition", default=0)
    lifo_stack_start_index: int = attr(name="lifoStackStartIndex", default=0)
    lifo_stack_end_index: int = attr(name="lifoStackEndIndex", default=0)
    start_time: str = attr(name="startTime", default="")
    end_time: str = attr(name="endTime", default="")
    duration: str = attr(default="")


class LifoStack(BaseXmlModel):
    index: int = attr()
    storage_location: str = attr(name="storageLocation")
    labwareType: str = attr(name="labwareType")
    labwareTotal: int = attr(name="labwareTotal")


class ParameterCollection(BaseXmlModel, tag="Parameters"):
    items: list[OverlordParameter] = element(tag="Parameter", default_factory=list)


class ReadTimeCollection(BaseXmlModel, tag="ReadTimes"):
    items: list[ReadTime] = element(tag="ReadTime", default_factory=list)


class LabwareCollection(BaseXmlModel, tag="LabwareCollection"):
    items: list[Labware] = element(tag="Labware", default_factory=list)


class LifoStackCollection(BaseXmlModel, tag="LifoStackCollection", skip_empty=True):
    items: list[LifoStack] = element(tag="LifoStack", default_factory=list)


class Batch(BaseXmlModel):
    created: "OverlordDatetime" = element(tag="Created", default_factory=datetime.now)
    start_after: "OverlordDatetime" = element(tag="StartAfter")
    added: str = element(tag="Added", default="0001-01-01_00-00-00")
    started: str = element(tag="Started", default="0001-01-01_00-00-00")
    completed: str = element(tag="Completed", default="0001-01-01_00-00-00")
    aborted: bool = element(tag="Aborted", default=False)
    abort_allowed: bool = element(tag="AbortAllowed", default=True)
    batch_name: str = element(tag="BatchName")
    parent_batch_name: str = element(tag="ParentBatchName")
    user: str = element(tag="User", default="_")
    user_data: str | None = element(tag="UserData", default=None)
    email: str | None = element(tag="Email", default=None)
    run_mode: int = element(tag="RunMode", default=1)
    batch_type: int = element(tag="BatchType", default=0)
    load_labware: bool = element(tag="LoadLabware", default=True)
    unload_labware: bool = element(tag="UnloadLabware", default=True)
    load_message: str | None = element(tag="LoadMessage", default=None)
    unload_message: str | None = element(tag="UnloadMessage", default=None)
    labware_estimated_duration: int = element(
        tag="LabwareEstimatedDuration", default=7200
    )

    parameters: ParameterCollection = element(default_factory=ParameterCollection)
    read_times: ReadTimeCollection = element(default_factory=ReadTimeCollection)
    labware: LabwareCollection = element(default_factory=LabwareCollection)
    lifo_stack: LifoStackCollection = element(default_factory=LifoStackCollection)


@dataclass
class OverlordBatchParams:
    wellplate_barcode: str
    plateread_id: int

    acquisition_name: str
    labware_type: str
    plate_location_start: str
    wellplate_storage_position: int
    scans_per_plate: int
    scan_time_interval: int
    cq1_protocol_name: str
    plate_estimated_time: int
    deadline: datetime

    def to_parameter_collection(self) -> ParameterCollection:
        return ParameterCollection(
            items=[
                OverlordParameter(
                    name="WELLPLATE_BARCODE", type="Text", value=self.wellplate_barcode
                ),
                OverlordParameter(
                    name="WELLPLATE_STORAGE_POSITION",
                    type="Numeric",
                    value=str(self.wellplate_storage_position),
                ),
                OverlordParameter(
                    name="PLATEREAD_ID", type="Numeric", value=str(self.plateread_id)
                ),
                OverlordParameter(
                    name="ACQUISITION_NAME", type="Text", value=self.acquisition_name
                ),
                OverlordParameter(
                    name="LABWARE_TYPE", type="Text", value=self.labware_type
                ),
                OverlordParameter(
                    name="PLATE_LOCATION_START",
                    type="Text",
                    value=self.plate_location_start,
                ),
                OverlordParameter(
                    name="SCANS_PER_PLATE",
                    type="Numeric",
                    value=str(self.scans_per_plate),
                ),
                OverlordParameter(
                    name="SCAN_TIME_INTERVAL",
                    type="Numeric",
                    value=str(self.scan_time_interval),
                ),
                OverlordParameter(
                    name="CQ1_PROTOCOL_NAME", type="Text", value=self.cq1_protocol_name
                ),
                OverlordParameter(
                    name="READ_BARCODES",
                    type="TrueFalse",
                    value="True" if self.wellplate_storage_position == -1 else "False",
                ),
                OverlordParameter(
                    name="PLATE_ESTIMATED_TIME",
                    type="Numeric",
                    value=str(self.plate_estimated_time),
                ),
                OverlordParameter(
                    name="DEADLINE",
                    type="Text",
                    value=self.deadline.isoformat(),
                ),
            ]
        )


""" overlord datetimes are a mess """


def zero_padded_overlord_dt_str(dt: datetime) -> str:
    dt = to_local_tz(dt)
    return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}_{dt.hour:02d}-{dt.minute:02d}-{dt.second:02d}"


OverlordDatetime = Annotated[
    datetime,
    PlainSerializer(zero_padded_overlord_dt_str, return_type=str),
]


def zero_padded_dt_str(dt: datetime) -> str:
    df = to_local_tz(dt)
    return f"{df.year:04d}-{df.month:02d}-{df.day:02d}T{df.hour:02d}:{df.minute:02d}:{df.second:02d}"


OtherOverlordDatetime = Annotated[
    datetime, PlainSerializer(zero_padded_dt_str, return_type=str)
]
