from enum import Enum
from typing import Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success
from sqlmodel import select

from app.acquisition import crud
from app.acquisition.models import Acquisition, AcquisitionCreate
from app.gsheet_integration.gsheet import RecordSheet, RowError


class CreateAcquisitionRecord(BaseModel):
    acquisition_name: str
    instrument_name: str


class CreateAcquisitionSheet(RecordSheet[CreateAcquisitionRecord]):
    def parse_row(
        self, row: dict[str, Any]
    ) -> Result[CreateAcquisitionRecord, RowError]:
        try:
            record = CreateAcquisitionRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    def handle_record(self, record: CreateAcquisitionRecord) -> Result[None, RowError]:
        acquisition = crud.get_acquisition_by_name(
            session=self.session, name=record.acquisition_name
        )
        if acquisition:
            return Failure(
                RowError(row=record.model_dump(), message="Acquisition already exists")
            )

        instrument = crud.get_instrument_by_name(
            session=self.session, name=record.instrument_name
        )
        if not instrument:
            return Failure(
                RowError(row=record.model_dump(), message="Instrument not found")
            )

        try:
            create = AcquisitionCreate(
                name=record.acquisition_name, instrument_id=instrument.id
            )
            crud.create_acquisition(session=self.session, acquisition_create=create)
            return Success(None)
        except Exception as e:
            return Failure(RowError(row=record.model_dump(), message=str(e)))

    def compile_updated_records(
        self, ignore: list[RowError]
    ) -> list[CreateAcquisitionRecord]:
        return []


class AcquisitionRecord(BaseModel):
    class AcquisitionRecordAction(str, Enum):
        none = "none"
        archive = "archive"

    acquisition_name: str
    instrument_name: str
    action: AcquisitionRecordAction

    @staticmethod
    def from_db(acquisition: Acquisition) -> "AcquisitionRecord":
        return AcquisitionRecord(
            acquisition_name=acquisition.name,
            instrument_name=acquisition.instrument.name,
            action=AcquisitionRecord.AcquisitionRecordAction.none,
        )


class AcquisitionSheet(RecordSheet[AcquisitionRecord]):
    def parse_row(self, row: dict[str, Any]) -> Result[AcquisitionRecord, RowError]:
        try:
            record = AcquisitionRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    def handle_record(self, record: AcquisitionRecord) -> Result[None, RowError]:
        match record.action:
            case AcquisitionRecord.AcquisitionRecordAction.archive:
                acquisition = crud.get_acquisition_by_name(
                    session=self.session, name=record.acquisition_name
                )
                if not acquisition:
                    return Failure(
                        RowError(
                            row=record.model_dump(), message="Acquisition not found"
                        )
                    )
                acquisition.is_active = False
                self.session.add(acquisition)
                self.session.commit()
                return Success(None)

            case AcquisitionRecord.AcquisitionRecordAction.none:
                return Success(None)

    def compile_updated_records(
        self, ignore: list[RowError]
    ) -> list[AcquisitionRecord]:
        err_row_names: list[str] = [err.row["acquisition_name"] for err in ignore]
        rows = self.session.exec(
            select(Acquisition)
            .where(Acquisition.name not in err_row_names)
            .where(Acquisition.is_active)
        ).all()
        records = [AcquisitionRecord.from_db(row) for row in rows]
        return sorted(records, key=lambda x: x.acquisition_name)


class ArchiveRecord(BaseModel):
    class ArchiveRecordAction(str, Enum):
        none = "none"
        retrieve = "retrieve"

    acquisition_name: str
    instrument_name: str
    action: ArchiveRecordAction

    @staticmethod
    def from_db(acquisition: Acquisition) -> "ArchiveRecord":
        return ArchiveRecord(
            acquisition_name=acquisition.name,
            instrument_name=acquisition.instrument.name,
            action=ArchiveRecord.ArchiveRecordAction.none,
        )


class ArchiveSheet(RecordSheet[ArchiveRecord]):
    def parse_row(self, row: dict[str, Any]) -> Result[ArchiveRecord, RowError]:
        try:
            record = ArchiveRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    def handle_record(self, record: ArchiveRecord) -> Result[None, RowError]:
        match record.action:
            case ArchiveRecord.ArchiveRecordAction.retrieve:
                acquisition = crud.get_acquisition_by_name(
                    session=self.session, name=record.acquisition_name
                )
                if not acquisition:
                    return Failure(
                        RowError(
                            row=record.model_dump(), message="Acquisition not found"
                        )
                    )
                acquisition.is_active = True
                self.session.add(acquisition)
                self.session.commit()
                return Success(None)

            case ArchiveRecord.ArchiveRecordAction.none:
                return Success(None)

    def compile_updated_records(self, ignore: list[RowError]) -> list[ArchiveRecord]:
        err_row_names: list[str] = [err.row["acquisition_name"] for err in ignore]
        rows = self.session.exec(
            select(Acquisition)
            .where(Acquisition.name not in err_row_names)
            .where(Acquisition.is_active == False)  # noqa: E712
        ).all()
        records = [ArchiveRecord.from_db(row) for row in rows]
        sorted_records = sorted(records, key=lambda x: x.acquisition_name)
        return sorted_records
