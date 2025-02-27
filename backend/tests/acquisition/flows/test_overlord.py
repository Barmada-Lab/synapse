from sqlmodel import Session

from app.acquisition.flows.acquisition_planning import implement_plan
from app.acquisition.flows.overlord import submit_plateread_spec
from app.acquisition.models import ProcessStatus
from tests.acquisition.utils import create_random_acquisition_plan


def test_submit_plateread_spec(db: Session) -> None:
    plan = create_random_acquisition_plan(session=db)
    plan = implement_plan(session=db, plan=plan)
    plateread = plan.reads[0]
    batch_path = submit_plateread_spec(session=db, spec=plateread)
    assert batch_path.exists()
    db.refresh(plateread)
    assert plateread.status == ProcessStatus.SCHEDULED
