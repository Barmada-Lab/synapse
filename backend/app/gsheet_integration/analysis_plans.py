from enum import Enum
from typing import Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success
from sqlmodel import select

from app.acquisition import crud
from app.acquisition.models import (
    Acquisition,
    AnalysisPlan,
    AnalysisTrigger,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecCreate,
    SlurmJobStatus,
)
from app.gsheet_integration.gsheet import RecordSheet, RowError


class CreateAnalysisPlanRecord(BaseModel):
    acquisition_name: str
    analysis_cmd: str
    analysis_args: str
    analysis_trigger: AnalysisTrigger
    trigger_value: int | None


class CreateAnalysisPlanSheet(RecordSheet[CreateAnalysisPlanRecord]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.acquisitions_created = set()

    def parse_row(
        self, row: dict[str, Any]
    ) -> Result[CreateAnalysisPlanRecord, RowError]:
        if row["trigger_value"] == "":
            row["trigger_value"] = None
        else:
            row["trigger_value"] = int(row["trigger_value"])
        try:
            record = CreateAnalysisPlanRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    def handle_record(self, record: CreateAnalysisPlanRecord) -> Result[None, RowError]:
        acquisition = crud.get_acquisition_by_name(
            session=self.session, name=record.acquisition_name
        )
        if not acquisition:
            return Failure(
                RowError(row=record.model_dump(), message="Acquisition not found")
            )
        self.acquisitions_created.add(acquisition.name)
        analysis_plan = acquisition.analysis_plan
        if not analysis_plan:
            analysis_plan = crud.create_analysis_plan(
                session=self.session,
                acquisition_id=acquisition.id,  # type: ignore[arg-type]
            )
        try:
            sbatch = SBatchAnalysisSpecCreate(
                trigger=record.analysis_trigger,
                trigger_value=record.trigger_value,
                analysis_cmd=record.analysis_cmd,
                analysis_args=record.analysis_args.split(","),
                analysis_plan_id=analysis_plan.id,
            )
            crud.create_analysis_spec(session=self.session, create=sbatch)
            return Success(None)
        except Exception as e:
            self.session.rollback()
            return Failure(RowError(row=record.model_dump(), message=str(e)))

    def compile_updated_records(
        self, ignore: list[RowError]
    ) -> list[CreateAnalysisPlanRecord]:
        return []


class AnalysisPlanRecord(BaseModel):
    class AnalysisPlanRecordAction(str, Enum):
        none = "none"
        delete = "delete"

    acquisition_name: str
    analysis_cmd: str
    analysis_args: str
    analysis_trigger: AnalysisTrigger
    trigger_value: int | None = None
    analysis_status: SlurmJobStatus
    action: AnalysisPlanRecordAction

    @staticmethod
    def from_db(spec: SBatchAnalysisSpec) -> "AnalysisPlanRecord":
        return AnalysisPlanRecord(
            acquisition_name=spec.analysis_plan.acquisition.name,
            analysis_cmd=spec.analysis_cmd,
            analysis_args=",".join(spec.analysis_args),
            analysis_trigger=spec.trigger,
            trigger_value=spec.trigger_value,
            analysis_status=spec.status,
            action=AnalysisPlanRecord.AnalysisPlanRecordAction.none,
        )


class AnalysisPlanSheet(RecordSheet[AnalysisPlanRecord]):
    def parse_row(self, row: dict[str, Any]) -> Result[AnalysisPlanRecord, RowError]:
        try:
            if row["trigger_value"] == "":
                row["trigger_value"] = None
            record = AnalysisPlanRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    def handle_record(self, record: AnalysisPlanRecord) -> Result[None, RowError]:
        match record.action:
            case AnalysisPlanRecord.AnalysisPlanRecordAction.delete:
                acquisition = crud.get_acquisition_by_name(
                    session=self.session, name=record.acquisition_name
                )
                if not acquisition or not acquisition.analysis_plan:
                    return Success(None)
                analysis_plan = acquisition.analysis_plan
                spec = crud.get_analysis_spec(
                    session=self.session,
                    analysis_plan_id=analysis_plan.id,  # type: ignore[arg-type]
                    analysis_cmd=record.analysis_cmd,
                    analysis_args=record.analysis_args.split(","),
                )
                if spec:
                    self.session.delete(spec)
                    self.session.commit()
                return Success(None)

            case AnalysisPlanRecord.AnalysisPlanRecordAction.none:
                return Success(None)

    def compile_updated_records(
        self, ignore: list[RowError]
    ) -> list[AnalysisPlanRecord]:
        records = []
        ignore_list = [
            (
                err.row["acquisition_name"],
                err.row["analysis_cmd"],
                err.row["analysis_args"],
            )
            for err in ignore
        ]

        for plan in self.session.exec(
            select(SBatchAnalysisSpec)
            .join(AnalysisPlan)
            .join(Acquisition)
            .where(Acquisition.is_active)
        ).all():
            record = AnalysisPlanRecord.from_db(plan)
            if (
                record.acquisition_name,
                record.analysis_cmd,
                ",".join(record.analysis_args),
            ) not in ignore_list:
                records.append(record)

        return sorted(records, key=lambda r: r.acquisition_name)
