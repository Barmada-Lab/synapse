from datetime import datetime, timedelta, timezone

from prefect import flow, get_run_logger, task
from sqlmodel import Session

from app.acquisition.flows.overlord import submit_plateread_spec
from app.acquisition.models import AcquisitionPlan, PlatereadSpec, ProcessStatus
from app.core.deps import get_db
from app.labware.models import Wellplate


@task
def implement_plan(
    session: Session, plan: AcquisitionPlan, start_time: datetime | None = None
) -> AcquisitionPlan:
    """
    Implements a plan by creating PlatereadSpecs based on the plan's parameters and current time.

    PlateReadSpecs are then scheduled for execution by the scheduler.
    """
    logger = get_run_logger()
    logger.info(f"Implementing acquisition plan for {plan.acquisition.name}")
    # not using the database clock here has the potential to cause issues
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    for i in range(plan.n_reads):
        start_after = start_time + (i * plan.interval)
        deadline = None
        if plan.deadline_delta:
            deadline = start_after + plan.deadline_delta
        else:
            deadline = start_after + timedelta(days=9999)
        session.add(
            PlatereadSpec(
                start_after=start_after,
                deadline=deadline,
                acquisition_plan_id=plan.id,
            )
        )
    session.commit()
    session.refresh(plan)
    return plan


@task
def schedule_unscheduled_reads(session: Session, plan: AcquisitionPlan):
    unscheduled_reads = [r for r in plan.reads if r.status == ProcessStatus.PENDING]
    for read in unscheduled_reads:
        submit_plateread_spec(session=session, spec=read)


@flow
def check_to_schedule_acquisition_plan(wellplate_id: int):
    logger = get_run_logger()
    with get_db() as session:
        logger.info(f"Checking to schedule plans for wellplate {wellplate_id}")
        wellplate = session.get(Wellplate, wellplate_id)
        if wellplate is None:
            raise ValueError(f"Wellplate {wellplate_id} not found")

        for plan in wellplate.acquisition_plans:
            if (
                plan.storage_location == wellplate.location
                and not plan.scheduled
                and not plan.completed
            ):
                # The plan may have already been implemented, but not scheduled.
                # Implemented plans will have reads associated with them
                if not any(plan.reads):
                    plan = implement_plan(session=session, plan=plan)
                schedule_unscheduled_reads(session=session, plan=plan)
