import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlmodel import Column, Enum, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.procedures.models import AcquisitionPlan

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

    collections: list["ArtifactCollection"] = Relationship(back_populates="acquisition")

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

    acquisition_id: int = Field(foreign_key="acquisition.id")
    acquisition: "Acquisition" = Relationship(back_populates="collections")


class ArtifactCollectionCreate(ArtifactCollectionBase):
    acquisition_id: int


class ArtifactCollectionRecord(ArtifactCollectionBase):
    id: int
