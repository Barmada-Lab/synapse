import enum
from datetime import datetime, timedelta
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Column, Enum, Field, Relationship, SQLModel

from app.labware.models import Location, Wellplate


class PlatereadStatus(str, enum.Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"  # user-initiated stop state
    ABORTED = "ABORTED"  # system-initiated stop state
    RESET = "RESET"


class ImagingPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"


### Acquisition Plan
################################################


class AcquisitionPlanBase(SQLModel):
    name: str = Field(unique=True, index=True, min_length=1, max_length=255)
    wellplate_id: int = Field(foreign_key="wellplate.id", ondelete="CASCADE")
    storage_location: Location
    protocol_name: str = Field(max_length=255)
    n_reads: int = Field(ge=1)
    interval: timedelta = Field(default=timedelta(days=0))
    deadline_delta: timedelta = Field(default=timedelta(days=0))
    priority: ImagingPriority = ImagingPriority.NORMAL


# table
class AcquisitionPlan(AcquisitionPlanBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    wellplate: Wellplate = Relationship(back_populates="acquisition_plans")

    protocol_name: str = Field(max_length=255)
    n_reads: int

    storage_location: Location = Field(sa_column=Column(Enum(Location), nullable=False))
    priority: ImagingPriority = Field(
        sa_column=Column(Enum(ImagingPriority), nullable=False),
        default=ImagingPriority.NORMAL,
    )

    schedule: list["PlatereadSpec"] = Relationship(
        back_populates="acquisition_plan", cascade_delete=True
    )

    # using Optional["AcquisitionArtifact"] because declaring
    # "AcquisitionArtifact" | None results in a TypeError
    acquisition: Optional["Acquisition"] = Relationship(
        back_populates="acquisition_plan",
    )


# read
class AcquisitionPlanRecord(AcquisitionPlanBase):
    id: int
    schedule: list["PlatereadSpecRecord"] = []


class AcquisitionPlanCreate(AcquisitionPlanBase):
    pass


class AcquisitionPlanList(SQLModel):
    data: list[AcquisitionPlanRecord]
    count: int


### Plate Read
################################################


class PlatereadSpecBase(SQLModel):
    start_after: datetime
    deadline: datetime | None
    status: PlatereadStatus = Field(
        sa_column=Column(Enum(PlatereadStatus), nullable=False),
        default=PlatereadStatus.PENDING,
    )


class PlatereadSpec(PlatereadSpecBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    acquisition_plan_id: int = Field(
        foreign_key="acquisitionplan.id", ondelete="CASCADE"
    )
    acquisition_plan: AcquisitionPlan = Relationship(back_populates="schedule")


class PlatereadSpecRecord(PlatereadSpecBase):
    id: int


class PlatereadSpecUpdate(SQLModel):
    status: PlatereadStatus


#################################################################################
# Acquisition model
# ---
# An Acquisition represents the result of a particular AcquisitionPlan. It may
# have a 1-1 relation with an AcquisitionPlan, but it may also exist independent
# of any AcquisitionPlan, as may be the case for manually acquired data or data
# acquired using an external system. Acquisitions are uniquely named, and mostly
# serve as a linking relation between groups of Artifacts and AcquisitionPlans.
#################################################################################


class AcquisitionBase(SQLModel):
    name: str = Field(unique=True, index=True, min_length=1, max_length=255)


class Acquisition(AcquisitionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    collections: list["ArtifactCollection"] = Relationship(
        back_populates="acquisition", cascade_delete=True
    )

    acquisition_plan_id: int | None = Field(foreign_key="acquisitionplan.id")
    acquisition_plan: Optional["AcquisitionPlan"] = Relationship(
        back_populates="acquisition"
    )


class AcquisitionCreate(AcquisitionBase):
    acquisition_plan_id: int | None = None


class AcquisitionRecord(AcquisitionBase):
    id: int
    artifacts: list["ArtifactCollectionRecord"] = []
    acquisition_plan: Optional["AcquisitionPlan"] = None


#################################################################################
# ArtifactCollection model
# ---
# An ArtifactCollection represents a concrete collection of data in a particular
# Repository that has been generated through acquisition or analysis. This record
# exists to facilitate automated data backup and retrieval, as well as
# reproducible analysis.
#################################################################################


class Repository(str, enum.Enum):
    ACQUISITION = "ACQUISITION"
    ARCHIVE = "ARCHIVE"
    ANALYSIS = "ANALYSIS"


class ArtifactType(str, enum.Enum):
    ACQUISITION = "ACQUISITION"
    ANALYSIS = "ANALYSIS"


class ArtifactCollectionBase(SQLModel):
    location: Repository = Field(sa_column=Column(Enum(Repository), nullable=False))
    artifact_type: ArtifactType = Field(
        sa_column=Column(Enum(ArtifactType), nullable=False)
    )
    record_created: datetime = Field(default_factory=datetime.now)
    last_update: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={
            "onupdate": sa.func.now(),
            "server_default": sa.func.now(),
        },
    )


class ArtifactCollection(ArtifactCollectionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    acquisition_id: int = Field(foreign_key="acquisition.id", ondelete="CASCADE")
    acquisition: "Acquisition" = Relationship(back_populates="collections")

    artifacts: list["Artifact"] = Relationship(
        back_populates="collection", cascade_delete=True
    )


class ArtifactCollectionCreate(ArtifactCollectionBase):
    acquisition_id: int


class ArtifactCollectionRecord(ArtifactCollectionBase):
    id: int


class ArtifactBase(SQLModel):
    name: str


class Artifact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str

    collection_id: int = Field(foreign_key="artifactcollection.id", ondelete="CASCADE")
    collection: ArtifactCollection = Relationship(back_populates="artifacts")


class ArtifactCreate(ArtifactBase):
    pass


class ArtifactRecord(ArtifactBase):
    id: int
