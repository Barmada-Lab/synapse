import pytest

from app.labware import flows


def test_print_barcode_too_long():
    barcode = "A" * 10
    with pytest.raises(ValueError) as e:
        flows.print_wellplate_barcode_task.fn(barcode)
        e.match("Barcode must be 1-9 characters in length")


def test_print_barcode_empty_string():
    barcode = ""
    with pytest.raises(ValueError) as e:
        flows.print_wellplate_barcode_task.fn(barcode)
        e.match("Barcode must be 1-9 characters in length")
