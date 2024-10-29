import enum
from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Column, Enum, Field, SQLModel


class WellplateType(str, enum.Enum):
    REVVITY_PHENOPLATE_96 = "REVVITY_PHENOPLATE_96"


class Location(str, enum.Enum):
    CQ1 = "CQ1"
    KX2 = "KX2"
    CYTOMAT2 = "CYTOMAT2"
    HOTEL = "HOTEL"


### WellPlate
############################################


# base
class WellplateRecord(SQLModel):
    name: str = Field(unique=True, index=True, max_length=255)
    plate_type: WellplateType
    location: Location | None
    record_created: datetime
    last_update: datetime


# table
class Wellplate(WellplateRecord, table=True):
    id: int | None = Field(default=None, primary_key=True)
    plate_type: WellplateType = Field(
        sa_column=Column(Enum(WellplateType), nullable=False)
    )
    location: Location | None = Field(
        default=None, sa_column=Column(Enum(Location), nullable=True)
    )

    record_created: datetime = Field(default_factory=datetime.now)
    last_update: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={
            "onupdate": sa.func.now(),
            "server_default": sa.func.now(),
        },
    )


# requests
class WellplateCreate(SQLModel):
    name: str
    plate_type: WellplateType


class WellplateUpdate(SQLModel):
    location: Location | None


class WellplateList(SQLModel):
    data: list[WellplateRecord]
    count: int
