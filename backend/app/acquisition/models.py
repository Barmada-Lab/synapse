import enum
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import sqlalchemy as sa
from pydantic import computed_field
from sqlmodel import Column, Enum, Field, Relationship, SQLModel

from app.acquisition.consts import TAR_ZST_EXTENSION
from app.core.config import settings
from app.labware.models import Location, Wellplate


class ProcessStatus(str, enum.Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"  # user-initiated stop state
    ABORTED = "ABORTED"  # system-initiated stop state
    RESET = "RESET"

    @property
    def is_endstate(self) -> bool:
        return self in [
            ProcessStatus.COMPLETED,
            ProcessStatus.CANCELLED,
            ProcessStatus.ABORTED,
        ]


class SlurmJobStatus(str, enum.Enum):
    UNSUBMITTED = "UNSUBMITTED"
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    UNHANDLED = "UNHANDLED"


class ImagingPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"


class Repository(str, enum.Enum):
    ACQUISITION_STORE = "ACQUISITION_STORE"
    ARCHIVE_STORE = "ARCHIVE_STORE"
    ANALYSIS_STORE = "ANALYSIS_STORE"

    @property
    def path(self) -> Path:
        match self:
            case Repository.ACQUISITION_STORE:
                return settings.ACQUISITION_DIR
            case Repository.ARCHIVE_STORE:
                return settings.ARCHIVE_DIR
            case Repository.ANALYSIS_STORE:
                return settings.ANALYSIS_DIR


class ArtifactType(str, enum.Enum):
    ACQUISITION_DATA = "ACQUISITION_DATA"
    ANALYSIS_DATA = "ANALYSIS_DATA"


class AnalysisTrigger(str, enum.Enum):
    END_OF_RUN = "END_OF_RUN"
    POST_READ = "POST_READ"
    IMMEDIATE = "IMMEDIATE"


#################################################################################
# Instruments
#################################################################################


class InstrumentTypeBase(SQLModel):
    name: str = Field(unique=True, index=True, min_length=1, max_length=255)


class InstrumentType(InstrumentTypeBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    instruments: list["Instrument"] = Relationship(back_populates="instrument_type")


class InstrumentTypeCreate(InstrumentTypeBase):
    pass


class InstrumentTypeRecord(InstrumentTypeBase):
    id: int


class InstrumentTypeList(SQLModel):
    data: list[InstrumentTypeRecord]
    count: int


class InstrumentBase(SQLModel):
    name: str = Field(unique=True, index=True, min_length=1, max_length=255)


class Instrument(InstrumentBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    instrument_type_id: int = Field(foreign_key="instrumenttype.id", ondelete="CASCADE")
    instrument_type: InstrumentType = Relationship(back_populates="instruments")

    acquisitions: list["Acquisition"] = Relationship(back_populates="instrument")


class InstrumentCreate(InstrumentBase):
    instrument_type_id: int


class InstrumentRecord(InstrumentBase):
    id: int


class InstrumentList(SQLModel):
    data: list[InstrumentRecord]
    count: int


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
    is_active: bool = Field(default=True)


class Acquisition(AcquisitionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    collections_list: list["ArtifactCollection"] = Relationship(
        back_populates="acquisition", cascade_delete=True
    )

    instrument_id: int = Field(foreign_key="instrument.id", ondelete="CASCADE")
    instrument: Instrument = Relationship(back_populates="acquisitions")

    acquisition_plan: Optional["AcquisitionPlan"] = Relationship(
        back_populates="acquisition", cascade_delete=True
    )
    analysis_plan: Optional["AnalysisPlan"] = Relationship(
        back_populates="acquisition", cascade_delete=True
    )

    def get_collection(
        self, artifact_type: ArtifactType, location: Repository
    ) -> Optional["ArtifactCollection"]:
        return next(
            (
                collection
                for collection in self.collections_list
                if collection.artifact_type == artifact_type
                and collection.location == location
            ),
            None,
        )


class AcquisitionCreate(AcquisitionBase):
    instrument_id: int


class AcquisitionRecord(AcquisitionBase):
    id: int
    artifacts: list["ArtifactCollectionRecord"] = []
    acquisition_plan: Optional["AcquisitionPlanRecord"] = None
    analysis_plan: Optional["AnalysisPlanRecord"] = None


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


"""

Artifact collections are directories of related data stored in an acquisition
directory. There are two artifact collection types: acquisition, and analysis.
Acquisition artifact collections contain raw acquisition data, and analysis
artifact collections contain data derived from the raw acquisition data.
Artifact collections additionally have a location field, which specifies the
repository in which the collection is stored. The repository has a
corresponding local path on the server, which is used to locate the data.

Example directory structure:

/analysis
    /acquisition_name
        /acquisition
        /analysis

/archive
    /acquisition_name
        /acquisition.tar.zst

"""


class ArtifactCollection(ArtifactCollectionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    acquisition_id: int = Field(foreign_key="acquisition.id", ondelete="CASCADE")
    acquisition: Acquisition = Relationship(back_populates="collections_list")

    __table_args__ = (
        sa.UniqueConstraint(
            "acquisition_id",
            "artifact_type",
            "location",
            name="unique_acquisition_collection",
        ),
    )

    @computed_field  # type: ignore
    @property
    def acquisition_dir(self) -> Path:
        return get_acquisition_path(self.location, self.acquisition.name)

    @computed_field  # type: ignore
    @property
    def path(self) -> Path:
        return get_artifact_collection_path(
            self.location, self.acquisition.name, self.artifact_type
        )


class ArtifactCollectionCreate(ArtifactCollectionBase):
    acquisition_id: int


class ArtifactCollectionRecord(ArtifactCollectionBase):
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
    deadline_delta: timedelta | None = None
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

    status: SlurmJobStatus = Field(
        sa_column=Column(Enum(SlurmJobStatus), nullable=False),
        default=SlurmJobStatus.UNSUBMITTED,
    )
    analysis_cmd: str = Field(max_length=255)
    analysis_args: list[str] = Field(
        sa_column=Column(sa.ARRAY(sa.String), nullable=False), default_factory=list
    )

    analysis_plan_id: int = Field(foreign_key="analysisplan.id", ondelete="CASCADE")
    analysis_plan: AnalysisPlan = Relationship(back_populates="sbatch_analyses")

    __table_args__ = (
        sa.UniqueConstraint(
            "analysis_plan_id",
            "analysis_cmd",
            "analysis_args",
            name="unique_sbatch_analysis_per_plan",
        ),
    )


class SBatchAnalysisSpecCreate(SBatchAnalysisSpecBase):
    analysis_plan_id: int


class SBatchAnalysisSpecRecord(SBatchAnalysisSpecBase):
    id: int
    status: SlurmJobStatus


class SBatchAnalysisSpecUpdate(SQLModel):
    status: SlurmJobStatus


def get_acquisition_path(repository: Repository, acquisition_name: str) -> Path:
    return repository.path / acquisition_name


def get_artifact_collection_path(
    repository: Repository, acquisition_name: str, artifact_type: ArtifactType
) -> Path:
    acquisition_path = get_acquisition_path(repository, acquisition_name)
    artifact_collection_file = artifact_type.value.lower()
    if repository == Repository.ARCHIVE_STORE:
        artifact_collection_file += TAR_ZST_EXTENSION
    return acquisition_path / artifact_collection_file
