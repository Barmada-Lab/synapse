from datetime import timedelta
from typing import Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success
from sqlmodel import asc, select

from app.acquisition.models import (
    Acquisition,
    AcquisitionPlan,
    PlatereadSpec,
    ProcessStatus,
)

from .gsheet import RecordSheet, RowError


class PlatereadRecord(BaseModel):
    plateread_name: str
    start_time: str
    end_time: str
    status: ProcessStatus


class ReadsSheet(RecordSheet[PlatereadRecord]):
    def parse_row(self, row: dict[str, Any]) -> Result[PlatereadRecord, RowError]:
        try:
            record = PlatereadRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    # this sheet don't do sheet
    def handle_record(self, record: PlatereadRecord) -> Result[None, RowError]:
        return Success(None)

    def compile_updated_records(self, ignore: list[RowError]) -> list[PlatereadRecord]:
        db_specs = list(
            self.session.exec(
                select(PlatereadSpec)
                .join(AcquisitionPlan)
                .join(Acquisition)
                .where(Acquisition.is_active)
                .order_by(asc(PlatereadSpec.start_after))
            ).all()
        )

        records = []
        last_end_time = db_specs[0].start_after
        SURVIVAL_DURATION = timedelta(minutes=50)
        for spec in db_specs:
            start_time = max(last_end_time, spec.start_after)
            end_time = start_time + SURVIVAL_DURATION
            last_end_time = end_time

            spec_idx = (
                sorted(spec.acquisition_plan.reads, key=lambda x: x.start_after).index(
                    spec
                )
                + 1
            )
            plateread_name = f"{spec.acquisition_plan.acquisition.name} {spec_idx}"

            record = PlatereadRecord(
                plateread_name=plateread_name,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                status=spec.status,
            )
            records.append(record)

        return records
