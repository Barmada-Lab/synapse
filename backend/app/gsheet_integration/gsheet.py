from abc import ABC, abstractmethod
from typing import Any

import gspread
import numpy as np
import pandas as pd
from gspread_formatting import (  # type: ignore[import-untyped]
    CellFormat,
    Color,
    TextFormat,
    format_cell_ranges,
)
from pydantic import BaseModel
from returns.result import Failure, Result
from sqlmodel import Session

bg0_h = Color.fromHex("#f9f5d7")
bg1 = Color.fromHex("#ebdbb2")
fg = Color.fromHex("#3c3836")
red = Color.fromHex("#cc241d")
green = Color.fromHex("#98971a")

header_fmt = CellFormat(
    backgroundColor=green,
    textFormat=TextFormat(foregroundColor=bg0_h, bold=True),
)

param_fmt = CellFormat(
    backgroundColor=bg1,
    textFormat=TextFormat(foregroundColor=fg, bold=False),
)

err_fmt = CellFormat(
    backgroundColor=red,
    textFormat=TextFormat(foregroundColor=bg0_h, bold=True),
)


class RowError(BaseModel):
    row: dict[str, Any]
    message: str

    @property
    def row_with_error(self) -> dict[str, Any]:
        row = self.row.copy()
        row["error"] = self.message
        return row


class RecordSheet[T: BaseModel](ABC):
    def __init__(self, ws: gspread.Worksheet, session: Session):
        self.df = pd.DataFrame(ws.get_all_records())
        self.df["error"] = np.nan
        self.session = session

    @abstractmethod
    def parse_row(self, row: dict[str, Any]) -> Result[T, RowError]:
        ...

    @abstractmethod
    def handle_record(self, record: T) -> Result[None, RowError]:
        """
        Handles a record action, performing side-effects. Errors are written to
        self.df
        """

    @abstractmethod
    def compile_updated_records(self, ignore: list[RowError]) -> list[T]:
        ...

    def process_sheet(self) -> None:
        errors = []
        for _, row in self.df.iterrows():
            row_dict = row.to_dict()
            result = self.parse_row(row_dict).bind(self.handle_record)
            match result:
                case Failure(err):
                    errors.append(err)
        error_dicts = [err.row_with_error for err in errors]
        updated_records = self.compile_updated_records(errors)
        record_dicts = [record.model_dump() for record in updated_records]
        self.df = pd.DataFrame.from_records(error_dicts + record_dicts).fillna("")
        if "error" not in self.df.columns:
            self.df["error"] = np.nan

    def render(self, ws: gspread.Worksheet) -> None:
        ws.clear_notes(["A1:A"])
        if ws.row_count > 2:
            ws.batch_clear(["A2:Z"])
            ws.delete_rows(3, ws.row_count)
        elif ws.row_count == 2 and ws.get("A2:Z2") != [[]]:
            ws.batch_clear(["A2:Z2"])
        else:
            # avoid calling batch_clear on an empty range, as it removes data validation for some reason
            pass
        format_cell_ranges(ws, [("A1:Z1", header_fmt), ("A2:Z", param_fmt)])

        out_df = self.df.drop(columns=["error"])
        rows = [list(row) for row in out_df.itertuples(index=False)]
        ws.append_rows(rows, value_input_option="USER_ENTERED")  # type: ignore

        errors = self.df["error"]
        error_idxs = np.where(errors.notna())[0]

        if error_idxs.size > 0:
            fmt_ranges = [(f"A{idx + 2}:Z{idx + 2}", err_fmt) for idx in error_idxs]
            format_cell_ranges(ws, fmt_ranges)

            a_cells = [f"A{idx + 2}" for idx in error_idxs]
            notes = dict(zip(a_cells, errors.iloc[error_idxs], strict=True))
            ws.insert_notes(notes)
