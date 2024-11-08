import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Column, Enum, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.acquisition.models import AcquisitionPlan


### WellPlate
############################################


class WellplateType(str, enum.Enum):
    REVVITY_PHENOPLATE_96 = "REVVITY_PHENOPLATE_96"


class Location(str, enum.Enum):
    CQ1 = "CQ1"
    KX2 = "KX2"
    CYTOMAT2 = "CYTOMAT2"
    HOTEL = "HOTEL"
    EXTERNAL = "EXTERNAL"


# base
class WellplateBase(SQLModel):
    name: str = Field(unique=True, index=True, min_length=1, max_length=9)
    plate_type: WellplateType
    location: Location
    record_created: datetime


# table
class Wellplate(WellplateBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    plate_type: WellplateType = Field(
        sa_column=Column(Enum(WellplateType), nullable=False)
    )
    location: Location = Field(
        default=Location.EXTERNAL, sa_column=Column(Enum(Location), nullable=False)
    )

    record_created: datetime = Field(default_factory=datetime.now)

    acquisition_plans: list["AcquisitionPlan"] = Relationship(
        back_populates="wellplate", cascade_delete=True
    )


# requests
class WellplateCreate(SQLModel):
    name: str = Field(min_length=1, max_length=9)
    plate_type: WellplateType


class WellplateUpdate(SQLModel):
    location: Location


class WellplateRecord(WellplateBase):
    id: int


class WellplateList(SQLModel):
    data: list[WellplateRecord]
    count: int
