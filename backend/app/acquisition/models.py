import enum
from datetime import datetime, timedelta
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Column, Enum, Field, Relationship, SQLModel

from app.labware.models import Location, Wellplate


class ProcessStatus(str, enum.Enum):
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


class Repository(str, enum.Enum):
    ACQUISITION = "ACQUISITION"
    ARCHIVE = "ARCHIVE"
    ANALYSIS = "ANALYSIS"


class ArtifactType(str, enum.Enum):
    ACQUISITION = "ACQUISITION"
    ANALYSIS = "ANALYSIS"


class AnalysisTrigger(str, enum.Enum):
    POST_ACQUISTION = "POST_ACQUISITION"
    POST_READ = "POST_READ"


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

    acquisition_plan: Optional["AcquisitionPlan"] = Relationship(
        back_populates="acquisition", cascade_delete=True
    )
    analysis_plan: Optional["AnalysisPlan"] = Relationship(
        back_populates="acquisition", cascade_delete=True
    )


class AcquisitionCreate(AcquisitionBase):
    pass


class AcquisitionRecord(AcquisitionBase):
    id: int
    artifacts: list["ArtifactCollectionRecord"] = []
    acquisition_plan: Optional["AcquisitionPlan"] = None


class AcquisitionList(SQLModel):
    data: list[AcquisitionRecord]
    count: int


#################################################################################
# ArtifactCollection model
# ---
# An ArtifactCollection represents a concrete collection of data in a particular
# Repository that has been generated through acquisition or analysis. This record
# exists to facilitate automated data backup and retrieval, as well as
# reproducible analysis.
#################################################################################


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
    acquisition: Acquisition = Relationship(back_populates="collections")

    artifacts: list["Artifact"] = Relationship(
        back_populates="collection", cascade_delete=True
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "acquisition_id",
            "artifact_type",
            "location",
            name="unique_acquisition_collection",
        ),
    )


class ArtifactCollectionCreate(ArtifactCollectionBase):
    pass


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


#################################################################################
# Acquisition Plan
# ---
#################################################################################


class AcquisitionPlanBase(SQLModel):
    wellplate_id: int = Field(foreign_key="wellplate.id", ondelete="CASCADE")
    storage_location: Location
    protocol_name: str = Field(max_length=255)
    n_reads: int = Field(ge=1)
    interval: timedelta = Field(default=timedelta(days=0))
    deadline_delta: timedelta = Field(default=timedelta(days=0))
    priority: ImagingPriority = ImagingPriority.NORMAL


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

    acquisition_id: int = Field(
        foreign_key="acquisition.id", ondelete="CASCADE", unique=True
    )
    acquisition: Acquisition = Relationship(
        back_populates="acquisition_plan",
    )


class AcquisitionPlanRecord(AcquisitionPlanBase):
    id: int
    schedule: list["PlatereadSpecRecord"] = []


class AcquisitionPlanCreate(AcquisitionPlanBase):
    acquisition_id: int


class AcquisitionPlanList(SQLModel):
    data: list[AcquisitionPlanRecord]
    count: int


#################################################################################
# PlatereadSpec
# ---
#################################################################################


class PlatereadSpecBase(SQLModel):
    start_after: datetime
    deadline: datetime | None
    status: ProcessStatus = Field(
        sa_column=Column(Enum(ProcessStatus), nullable=False),
        default=ProcessStatus.PENDING,
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
    status: ProcessStatus


#################################################################################
# AnalysisPlan model
# ---
# An AnalysisPlan represents a set of instructions for processing and analyzing
# data. It is associated with an Acquisition.
#################################################################################


class AnalysisPlan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    acquisition_id: int = Field(
        foreign_key="acquisition.id", ondelete="CASCADE", unique=True
    )
    acquisition: Acquisition = Relationship(back_populates="analysis_plan")
    sbatch_analyses: list["SBatchAnalysisSpec"] = Relationship(
        back_populates="analysis_plan", cascade_delete=True
    )


class AnalysisPlanCreate(SQLModel):
    acquisition_id: int


class AnalysisPlanRecord(SQLModel):
    id: int
    sbatch_analyses: list["SBatchAnalysisSpecRecord"]


class SBatchAnalysisSpecBase(SQLModel):
    trigger: AnalysisTrigger
    trigger_value: int | None = None
    analysis_cmd: str
    analysis_args: list[str]


class SBatchAnalysisSpec(SBatchAnalysisSpecBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    trigger: AnalysisTrigger = Field(
        sa_column=Column(Enum(AnalysisTrigger), nullable=False)
    )
    trigger_value: int | None

    analysis_status: ProcessStatus = Field(
        sa_column=Column(Enum(ProcessStatus), nullable=False),
        default=ProcessStatus.PENDING,
    )
    analysis_cmd: str = Field(max_length=255)
    analysis_args: list[str] = Field(
        sa_column=Column(sa.ARRAY(sa.String), nullable=False), default_factory=list
    )

    analysis_plan_id: int = Field(foreign_key="analysisplan.id", ondelete="CASCADE")
    analysis_plan: AnalysisPlan = Relationship(back_populates="sbatch_analyses")


class SBatchAnalysisSpecCreate(SBatchAnalysisSpecBase):
    analysis_plan_id: int


class SBatchAnalysisSpecRecord(SBatchAnalysisSpecBase):
    id: int
    analysis_status: ProcessStatus
