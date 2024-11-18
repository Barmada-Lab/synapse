import logging
import socket
from collections.abc import Generator
from contextlib import contextmanager

from .config import settings

logger = logging.getLogger(__name__)


class BarcodePrinter:
    def __init__(self, *, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __enter__(self):
        self.sock.connect((self.host, self.port))
        return self

    def print_zpl(self, label: str):
        logger.debug(f"Printing zpl: {label}")
        self.sock.send(label.encode())

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sock.close()


@contextmanager
def get_barcode_printer() -> Generator[BarcodePrinter, None, None]:
    with BarcodePrinter(
        host=settings.ZPL_PRINTER_HOST, port=settings.ZPL_PRINTER_PORT
    ) as printer:
        yield printer
