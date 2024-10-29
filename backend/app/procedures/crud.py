from datetime import datetime

from sqlmodel import Session, select

from app.labware.models import Wellplate

from .models import AcquisitionPlan, AcquisitionPlanCreate, PlateReadSpec


def create_acquisition_plan(
    *, session: Session, plan_create: AcquisitionPlanCreate
) -> AcquisitionPlan:
    wellplate_id = plan_create.wellplate_id
    if session.get(Wellplate, wellplate_id) is None:
        raise ValueError(f"Wellplate {wellplate_id} not found")

    acquisition_plan = AcquisitionPlan.model_validate(plan_create)
    session.add(acquisition_plan)
    session.commit()
    session.refresh(acquisition_plan)
    return acquisition_plan


def get_acquisition_plan_by_name(
    *, session: Session, name: str
) -> AcquisitionPlan | None:
    stmt = select(AcquisitionPlan).where(AcquisitionPlan.name == name)
    return session.exec(stmt).first()


def schedule_plan(*, session: Session, plan: AcquisitionPlan) -> AcquisitionPlan:
    start_time = datetime.now()
    for i in range(plan.n_reads):
        start_after = start_time + (i * plan.interval)
        deadline = start_time + i * plan.interval + plan.deadline_delta
        session.add(
            PlateReadSpec(
                start_after=start_after,
                deadline=deadline,
                acquisition_plan_id=plan.id,
            )
        )
    session.commit()
    session.refresh(plan)
    return plan
