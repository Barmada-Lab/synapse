from datetime import datetime
from typing import Annotated, Literal

from pydantic.dataclasses import dataclass
from pydantic.functional_validators import BeforeValidator
from pydantic_xml import BaseXmlModel, attr, element

OVERLORD_STRFMT = "%Y-%m-%d_%H-%M-%S"

def parse_overlord_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.strptime(value, OVERLORD_STRFMT)


OverlordDatetime = Annotated[datetime, BeforeValidator(parse_overlord_datetime)]


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
    value: datetime = element(tag="Value")


class Labware(BaseXmlModel):
    index: int = attr()
    type: str = attr()
    barcode: str = attr()
    random_access_position: int = attr(name="randomAccessPosition")
    lifo_stack_start_index: int = attr(name="lifoStackStartIndex")
    lifo_stack_end_index: int = attr(name="lifoStackEndIndex")
    start_location: str = attr(name="startLocation")
    end_location: str = attr(name="endLocation")
    start_time: str = attr(name="startTime")
    end_time: str = attr(name="endTime")
    duration: str = attr()


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

    created: OverlordDatetime = element(tag="Created", default_factory=datetime.now)
    start_after: OverlordDatetime = element(tag="StartAfter")
    added: OverlordDatetime = element(tag="Added", default=datetime(1970, 1, 1))
    started: OverlordDatetime = element(tag="Started", default=datetime(1970, 1, 1))
    completed: OverlordDatetime = element(tag="Completed", default=datetime(1970, 1, 1))
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
    labware_estimated_duration: int = element(tag="LabwareEstimatedDuration", default=7200)

    parameters: ParameterCollection = element(default_factory=ParameterCollection)
    read_times: ReadTimeCollection = element(default_factory=ReadTimeCollection)
    labware: LabwareCollection = element(default_factory=LabwareCollection)
    lifo_stack: LifoStackCollection = element(default_factory=LifoStackCollection)


@dataclass
class OverlordBatchParams:
    wellplate_id: int
    plateread_id: int

    read_index: int
    read_total: int
    user_first_name: str
    user_last_name: str
    user_email: str
    user_data: str
    batch_name: str
    acquisition_name: str
    labware_type: str
    plate_total: int
    plate_location_start: str
    scans_per_plate: int
    scan_time_interval: int
    cq1_protocol_name: str
    read_barcodes: bool
    plate_estimated_time: int

    def to_parameter_collection(self) -> ParameterCollection:
        return ParameterCollection(
            items=[
                OverlordParameter(
                    name="WELLPLATE_ID", type="Text", value=str(self.wellplate_id)
                ),
                OverlordParameter(
                    name="PLATEREAD_ID", type="Numeric", value=str(self.plateread_id)
                ),
                OverlordParameter(
                    name="READ_INDEX", type="Numeric", value=str(self.read_index)
                ),
                OverlordParameter(
                    name="READ_TOTAL", type="Numeric", value=str(self.read_total)
                ),
                OverlordParameter(
                    name="USER_FIRST_NAME", type="Text", value=self.user_first_name
                ),
                OverlordParameter(
                    name="USER_LAST_NAME", type="Text", value=self.user_last_name
                ),
                OverlordParameter(
                    name="USER_EMAIL", type="Text", value=self.user_email
                ),
                OverlordParameter(name="USER_DATA", type="Text", value=self.user_data),
                OverlordParameter(
                    name="BATCH_NAME", type="Text", value=self.batch_name
                ),
                OverlordParameter(
                    name="ACQUISITION_NAME", type="Text", value=self.acquisition_name
                ),
                OverlordParameter(
                    name="LABWARE_TYPE", type="Text", value=self.labware_type
                ),
                OverlordParameter(
                    name="PLATE_TOTAL", type="Numeric", value=str(self.plate_total)
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
                    value="True" if self.read_barcodes else "False",
                ),
                OverlordParameter(
                    name="PLATE_ESTIMATED_TIME",
                    type="Numeric",
                    value=str(self.plate_estimated_time),
                ),
            ]
        )