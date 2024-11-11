from datetime import datetime
from typing import Annotated, Literal

from pydantic.functional_validators import BeforeValidator
from pydantic_xml import BaseXmlModel, attr, element


def parse_overlord_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d_%H-%M-%S")


OverlordDatetime = Annotated[datetime, BeforeValidator(parse_overlord_datetime)]


class OverlordParameter(BaseXmlModel):
    name: str = element(tag="Name")
    type: Literal["Text"] | Literal["Numeric"] | Literal["TrueFalse"] = element(
        tag="Type"
    )
    value: str | None = element(tag="Value", default=None)
    include_in_summary: bool = element(tag="IncludeInSummary")


class ReadTime(BaseXmlModel):
    index: int = attr()
    interval: int = element(tag="Interval")
    # overlord uses a normal datetime format for this element...
    value: datetime = element(tag="Value")


class Labware(BaseXmlModel):
    index: str = attr()
    type: str = attr()
    barcode: str = attr()
    random_access_position: str = attr(name="randomAccessPosition")
    lifo_stack_start_index: str = attr(name="lifoStackStartIndex")
    lifo_stack_end_index: str = attr(name="lifoStackEndIndex")
    start_location: str = attr(name="startLocation")
    end_location: str = attr(name="endLocation")
    start_time: str = attr(name="startTime")
    end_time: str = attr(name="endTime")
    duration: str = attr()


class Batch(BaseXmlModel):
    created: OverlordDatetime = element(tag="Created")
    start_after: OverlordDatetime = element(tag="StartAfter")
    added: OverlordDatetime = element(tag="Added")
    started: OverlordDatetime = element(tag="Started")
    completed: OverlordDatetime = element(tag="Completed")
    aborted: bool = element(tag="Aborted")
    abort_allowed: bool = element(tag="AbortAllowed")
    batch_name: str = element(tag="BatchName")
    parent_batch_name: str = element(tag="ParentBatchName")
    user: str = element(tag="User")
    user_data: str = element(tag="UserData", default="")
    email: str = element(tag="Email")
    run_mode: int = element(tag="RunMode")
    batch_type: int = element(tag="BatchType")
    load_labware: bool = element(tag="LoadLabware")
    unload_labware: bool = element(tag="UnloadLabware")
    load_message: str | None = element(tag="LoadMessage", default=None)
    unload_message: str | None = element(tag="UnloadMessage", default=None)
    labware_estimated_duration: int = element(tag="LabwareEstimatedDuration")

    class ParameterCollection(BaseXmlModel, tag="Parameters"):
        items: list[OverlordParameter] = element(tag="Parameter")

    class ReadTimeCollection(BaseXmlModel, tag="ReadTimes"):
        items: list[ReadTime] = element(tag="ReadTime")

    class LabwareCollection(BaseXmlModel, tag="LabwareCollection"):
        items: list[Labware] = element(tag="Labware")

    class LifoStackCollection(BaseXmlModel, tag="LifoStackCollection", skip_empty=True):
        pass

    parameters: ParameterCollection
    read_times: ReadTimeCollection
    labware: LabwareCollection
    lifo_stack: LifoStackCollection
