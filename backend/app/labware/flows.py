from prefect import flow

from app.core.printer import get_barcode_printer


@flow
def print_wellplate_barcode(barcode: str):
    if not (1 < len(barcode) < 10):
        raise ValueError("Barcode must be 1-9 characters in length")

    zpl = (
        "^XA"  # Start label
        "^LL84^PW600"  # Set length and width of label to 84x600 dots
        "^FO24,24,^BY3"  # Set field origin to 24,24 and module width to 3 dots
        f"^BCN,84,N,N,N,N,A^FD{barcode}"  # Create barcode field
        "^FS^FO400,24"  # Field separator, set next field origin to 400,24
        f"^A0,84,30^FB200,1,0,R,0^FD{barcode}"  # Create human readable field to the right of the barcode
        "^XZ"  # End label
    )

    with get_barcode_printer() as printer:
        printer.print_zpl(zpl)


def get_deployments():
    return [print_wellplate_barcode.to_deployment(name="print-wellplate-barcode")]
