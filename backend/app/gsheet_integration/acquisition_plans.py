from datetime import timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success
from sqlmodel import select

from app.acquisition import crud as acq_crud
from app.acquisition.models import (
    Acquisition,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    ProcessStatus,
)
from app.gsheet_integration.gsheet import RecordSheet, RowError
from app.labware import crud as lw_crud
from app.labware.models import Location, WellplateCreate, WellplateType


class CreateAcquisitionPlanRecord(BaseModel):
    acquisition_name: str
    wellplate_name: str
    storage_location: Location
    n_reads: int
    interval_mins: int
    protocol_name: str


class CreateAcquisitionPlanSheet(RecordSheet[CreateAcquisitionPlanRecord]):
    def parse_row(
        self, row: dict[str, Any]
    ) -> Result[CreateAcquisitionPlanRecord, RowError]:
        try:
            record = CreateAcquisitionPlanRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    def handle_record(
        self, record: CreateAcquisitionPlanRecord
    ) -> Result[None, RowError]:
        acquisition = acq_crud.get_acquisition_by_name(
            session=self.session, name=record.acquisition_name
        )
        if not acquisition:
            return Failure(
                RowError(row=record.model_dump(), message="Acquisition not found")
            )
        if acquisition.acquisition_plan:
            return Failure(
                RowError(
                    row=record.model_dump(),
                    message="Acquisition plan already exists for this acquisition",
                )
            )
        wellplate = lw_crud.get_wellplate_by_name(
            session=self.session, name=record.wellplate_name
        )
        if not wellplate:
            try:
                wellplate = lw_crud.create_wellplate(
                    session=self.session,
                    wellplate_create=WellplateCreate(
                        name=record.wellplate_name,
                        plate_type=WellplateType.REVVITY_PHENOPLATE_96,
                    ),
                )
            except Exception as e:
                return Failure(RowError(row=record.model_dump(), message=str(e)))
        try:
            acq_crud.create_acquisition_plan(
                session=self.session,
                plan_create=AcquisitionPlanCreate(
                    acquisition_id=acquisition.id,
                    wellplate_id=wellplate.id,
                    storage_location=record.storage_location,
                    n_reads=record.n_reads,
                    interval=timedelta(minutes=record.interval_mins),
                    protocol_name=record.protocol_name,
                ),
            )
            return Success(None)
        except Exception as e:
            return Failure(RowError(row=record.model_dump(), message=str(e)))

    def compile_updated_records(
        self, ignore: list[RowError]
    ) -> list[CreateAcquisitionPlanRecord]:
        return []


class AcquisitionPlanRecord(BaseModel):
    class AcquisitionPlanRecordAction(str, Enum):
        none = "none"
        delete = "delete"

    acquisition_name: str
    wellplate_name: str
    storage_location: Location
    n_reads: int
    interval_mins: int
    protocol_name: str
    acquisition_status: ProcessStatus
    action: AcquisitionPlanRecordAction

    @staticmethod
    def from_db(plan: AcquisitionPlan) -> "AcquisitionPlanRecord":
        match plan.schedule:
            case []:
                status = ProcessStatus.PENDING
            case reads:
                end_states = [
                    read.status
                    in [
                        ProcessStatus.COMPLETED,
                        ProcessStatus.ABORTED,
                        ProcessStatus.CANCELLED,
                    ]
                    for read in reads
                ]
                if all(end_states):
                    status = ProcessStatus.COMPLETED
                elif any(end_states):
                    status = ProcessStatus.RUNNING
                else:
                    status = ProcessStatus.SCHEDULED

        return AcquisitionPlanRecord(
            acquisition_name=plan.acquisition.name,
            wellplate_name=plan.wellplate.name,
            storage_location=plan.storage_location,
            n_reads=plan.n_reads,
            interval_mins=int(plan.interval.total_seconds() / 60),
            protocol_name=plan.protocol_name,
            acquisition_status=status,
            action=AcquisitionPlanRecord.AcquisitionPlanRecordAction.none,
        )


class AcquisitionPlanSheet(RecordSheet[AcquisitionPlanRecord]):
    def parse_row(self, row: dict[str, Any]) -> Result[AcquisitionPlanRecord, RowError]:
        try:
            record = AcquisitionPlanRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    def handle_record(self, record: AcquisitionPlanRecord) -> Result[None, RowError]:
        match record.action:
            case AcquisitionPlanRecord.AcquisitionPlanRecordAction.delete:
                acquisition = acq_crud.get_acquisition_by_name(
                    session=self.session, name=record.acquisition_name
                )
                if not acquisition or not acquisition.acquisition_plan:
                    return Success(None)
                self.session.delete(acquisition.acquisition_plan)
                self.session.commit()
                return Success(None)

            case AcquisitionPlanRecord.AcquisitionPlanRecordAction.none:
                return Success(None)

    def compile_updated_records(
        self, ignore: list[RowError]
    ) -> list[AcquisitionPlanRecord]:
        ignore_list = [error.row["acquisition_name"] for error in ignore]
        plans = self.session.exec(
            select(AcquisitionPlan).join(Acquisition).where(Acquisition.is_active)
        ).all()
        records = [AcquisitionPlanRecord.from_db(plan) for plan in plans]
        filt = [
            record for record in records if record.acquisition_name not in ignore_list
        ]
        return filt
