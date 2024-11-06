from unittest.mock import patch

import pytest

from app.labware import flows


@pytest.fixture(scope="function")
def mock_get_printer():
    with patch("app.core.printer.BarcodePrinter") as mock_get_printer:
        yield mock_get_printer


def test_print_barcode(mock_get_printer):
    barcode = "A" * 9
    mock_printer = mock_get_printer.return_value
    flows.print_wellplate_barcode(barcode)
    mock_printer.__enter__.assert_called_once()
    mock_printer.__enter__().print_zpl.assert_called_once()


def test_print_barcode_too_long(mock_get_printer):
    barcode = "A" * 10
    mock_printer = mock_get_printer.return_value
    with pytest.raises(ValueError) as e:
        flows.print_wellplate_barcode(barcode)
        e.match("Barcode must be 1-9 characters in length")
    mock_printer.__enter__.assert_not_called()
    mock_printer.__enter__().print_zpl.assert_not_called()


def test_print_barcode_empty_string(mock_get_printer):
    barcode = ""
    mock_printer = mock_get_printer.return_value
    with pytest.raises(ValueError) as e:
        flows.print_wellplate_barcode(barcode)
        e.match("Barcode must be 1-9 characters in length")
    mock_printer.__enter__.assert_not_called()
    mock_printer.__enter__().print_zpl.assert_not_called()
