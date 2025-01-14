import gspread
from prefect import flow
from prefect.blocks.system import Secret
from prefect.events import DeploymentEventTrigger

from app.acquisition.crud import get_acquisition_by_name
from app.acquisition.flows.analysis import handle_analyses
from app.core.config import settings
from app.core.deps import get_db

from .acquisition_plans import AcquisitionPlanSheet, CreateAcquisitionPlanSheet
from .acquisitions import AcquisitionSheet, ArchiveSheet, CreateAcquisitionSheet
from .analysis_plans import AnalysisPlanSheet, CreateAnalysisPlanSheet
from .print_barcodes import PrintBarcodesSheet


def get_imaging_spreadsheet() -> gspread.Spreadsheet:
    token = Secret.load("google-sheets-token").get()  # type: ignore[union-attr]
    gc = gspread.service_account_from_dict(
        token, http_client=gspread.http_client.BackOffHTTPClient
    )
    return gc.open_by_key(settings.IMAGING_SPREADSHEET_ID)


@flow
def sync_google_sheets():
    spread = get_imaging_spreadsheet()
    with get_db() as session:
        create_acquisition_ws = spread.worksheet("create_acquisition")
        create_acquisition_sheet = CreateAcquisitionSheet(
            create_acquisition_ws, session
        )
        create_acquisition_sheet.process_sheet()
        create_acquisition_sheet.render(create_acquisition_ws)

        acquisition_ws = spread.worksheet("acquisitions")
        acquisition_sheet = AcquisitionSheet(acquisition_ws, session)
        acquisition_sheet.process_sheet()
        acquisition_sheet.render(acquisition_ws)

        archive_ws = spread.worksheet("archive")
        archive_sheet = ArchiveSheet(archive_ws, session)
        archive_sheet.process_sheet()
        archive_sheet.render(archive_ws)
        # run it back
        acquisition_ws = spread.worksheet("acquisitions")
        acquisition_sheet.render(acquisition_ws)

        create_acquisition_ws = spread.worksheet("create_acquisition_plan")
        create_acquisition_plan_sheet = CreateAcquisitionPlanSheet(
            create_acquisition_ws, session
        )
        create_acquisition_plan_sheet.process_sheet()
        create_acquisition_plan_sheet.render(create_acquisition_ws)

        """
        NOTE: ALWAYS CREATE ACQUISITION PLANS BEFORE ANALYSIS PLANS
        """
        acquisition_plan_ws = spread.worksheet("acquisition_plans")
        acquisition_plan_sheet = AcquisitionPlanSheet(acquisition_plan_ws, session)
        acquisition_plan_sheet.process_sheet()
        acquisition_plan_sheet.render(acquisition_plan_ws)

        create_analysis_ws = spread.worksheet("create_analysis_plan")
        create_analysis_sheet = CreateAnalysisPlanSheet(create_analysis_ws, session)
        create_analysis_sheet.process_sheet()
        create_analysis_sheet.render(create_analysis_ws)

        analysis_ws = spread.worksheet("analysis_plans")
        analysis_sheet = AnalysisPlanSheet(analysis_ws, session)
        analysis_sheet.process_sheet()
        analysis_sheet.render(analysis_ws)

        print_barcodes_ws = spread.worksheet("print_barcodes")
        print_barcodes_sheet = PrintBarcodesSheet(print_barcodes_ws, session)
        print_barcodes_sheet.process_sheet()
        print_barcodes_sheet.render(print_barcodes_ws)

        # ... lastly,
        for acquisition_name in create_analysis_sheet.acquisitions_created:
            acquisition = get_acquisition_by_name(
                session=session, name=acquisition_name
            )
            handle_analyses(acquisition, session)


def get_deployments():
    return [
        sync_google_sheets.to_deployment(
            name="sync-google-sheets",
            triggers=[
                DeploymentEventTrigger(
                    expect={"google-sheets.sync-requested"},
                    name="sync-google-sheets",
                )
            ],
        ),
    ]
