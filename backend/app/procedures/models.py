import enum
from datetime import datetime, timedelta
from enum import auto

from sqlmodel import Column, Enum, Field, Relationship, SQLModel

from app.labware.models import Location, Wellplate


class PlateReadStatus(enum.Enum):
    PENDING = auto()
    SCHEDULED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    CANCELLED = auto()  # user-initiated stop state
    ABORTED = auto()  # system-initiated stop state
    RESET = auto()


class ImagingPriority(enum.Enum):
    NORMAL = auto()
    LOW = auto()


### Acquisition Plan
################################################


class AcquisitionPlanBase(SQLModel):
    name: str = Field(unique=True, index=True, min_length=1, max_length=255)
    wellplate_id: int = Field(foreign_key="wellplate.id")
    storage_location: Location
    protocol_name: str = Field(max_length=255)
    n_reads: int = Field(ge=1)
    interval: timedelta = Field(default=timedelta(days=0))
    deadline_delta: timedelta = Field(default=timedelta(days=0))
    priority: ImagingPriority = ImagingPriority.NORMAL


# table
class AcquisitionPlan(AcquisitionPlanBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    wellplate: Wellplate = Relationship()

    protocol_name: str = Field(max_length=255)
    n_reads: int

    storage_location: Location = Field(sa_column=Column(Enum(Location), nullable=False))
    priority: ImagingPriority = Field(
        sa_column=Column(Enum(ImagingPriority), nullable=False),
        default=ImagingPriority.NORMAL,
    )

    scheduled_reads: list["PlateReadSpec"] = Relationship(
        back_populates="acquisition_plan"
    )


# read
class AcquisitionPlanRecord(AcquisitionPlanBase):
    id: int
    scheduled_reads: list["PlateReadSpec"] = []


class AcquisitionPlanCreate(AcquisitionPlanBase):
    pass


### Plate Read
################################################


class PlateReadSpec(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    start_after: datetime
    deadline: datetime | None

    status: PlateReadStatus = Field(
        sa_column=Column(Enum(PlateReadStatus), nullable=False),
        default=PlateReadStatus.PENDING,
    )

    acquisition_plan_id: int = Field(foreign_key="acquisitionplan.id")
    acquisition_plan: AcquisitionPlan = Relationship(back_populates="scheduled_reads")
