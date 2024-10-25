# import enum
# from datetime import datetime
# from pathlib import Path

# from sqlmodel import Column, Enum, Field, Relationship, SQLModel

# from app.models.labware import Microplate


# class AcquisitionSignal(enum.Enum):
#     RUN_QA = "run_qa"
#     RUN_ACQUISITION = "run_acquisition"


# class Acquisition(SQLModel, table=True):
#     id: int = Field(primary_key=True)
#     start_after: datetime
#     overlord_xml_ref: Path
#     post_acquisition_signals: list[AcquisitionSignal] = Field(
#         sa_column=Column(Enum(AcquisitionSignal))
#     )

#     acquisition_spec_id: int = Field(foreign_key="acquisitionspec.id")
#     acquisition_spec: "AcquisitionSpec" = Relationship(back_populates="acquisition_schedule")


# class AcquisitionSpec(SQLModel, table=True):
#     id: int = Field(primary_key=True)
#     name: str = Field(unique=True)
#     protocol_name: str

#     microplate_id: int = Field(foreign_key="microplate.id")
#     microplate: Microplate = Relationship()

#     acquisition_schedule: list[Acquisition] = Relationship()
