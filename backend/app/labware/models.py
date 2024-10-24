import enum
from datetime import datetime
from enum import auto

import sqlalchemy as sa
from sqlmodel import Column, Enum, Field, SQLModel


class WellPlateType(enum.Enum):
    REVVITY_PHENOPLATE_96 = auto()


class Location(enum.Enum):
    CQ1 = "CQ1"
    KX2 = "KX2"
    CYTOMAT2 = "CYTOMAT2"


### WellPlate
############################################


# table
class WellPlate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    plate_type: WellPlateType = Field(
        sa_column=Column(Enum(WellPlateType), nullable=False)
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
class WellPlateCreate(SQLModel):
    name: str
    plate_type: WellPlateType


class WellPlateUpdate(SQLModel):
    location: Location | None


# responses
class WellPlatePublic(SQLModel):
    name: str
    plate_type: WellPlateType
    location: Location | None
    record_created: datetime
    last_location_update: datetime


class WellPlateList(SQLModel):
    data: list[WellPlatePublic]
    count: int
