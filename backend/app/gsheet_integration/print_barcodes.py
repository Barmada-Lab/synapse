from typing import Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from app.gsheet_integration.gsheet import RecordSheet, RowError
from app.labware.flows import print_wellplate_barcode


class PrintBarcodeRecord(BaseModel):
    wellplate_name: str


class PrintBarcodesSheet(RecordSheet[PrintBarcodeRecord]):
    def parse_row(self, row: dict[str, Any]) -> Result[PrintBarcodeRecord, RowError]:
        try:
            record = PrintBarcodeRecord.model_validate(row)
            return Success(record)
        except Exception as e:
            return Failure(RowError(row=row, message=str(e)))

    def handle_record(self, record: PrintBarcodeRecord) -> Result[None, RowError]:
        try:
            print_wellplate_barcode(record.wellplate_name)
            return Success(None)
        except Exception as e:
            return Failure(RowError(row=record.model_dump(), message=str(e)))

    def compile_updated_records(self, ignore):
        return []
