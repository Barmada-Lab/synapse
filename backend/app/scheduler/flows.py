from datetime import datetime, timedelta, timezone

from prefect import flow, get_run_logger, task
from prefect.cache_policies import NONE
from sqlalchemy import asc, update
from sqlmodel import Session, select

from app.acquisition.models import (
    AcquisitionPlan,
    ImagingPriority,
    PlatereadSpec,
    ProcessStatus,
    Wellplate,
)
from app.core.deps import get_db
from app.scheduler.overlord import submit_plateread_spec


def any_platereads_running(session: Session) -> bool:
    statement = (
        select(PlatereadSpec)
        .where(PlatereadSpec.status == ProcessStatus.RUNNING)
        .limit(1)
    )
    return session.exec(statement).first() is not None


def cancel_past_deadline(session: Session):
    session.execute(
        update(PlatereadSpec)
        .where(PlatereadSpec.deadline < datetime.now(timezone.utc))  # type: ignore
        .values(status=ProcessStatus.CANCELLED)
    )
    session.commit()


def get_next_task(session: Session, start_after: datetime, priority: ImagingPriority):
    statement = (
        select(PlatereadSpec)
        .join(AcquisitionPlan)
        .join(Wellplate)
        .where(PlatereadSpec.status == ProcessStatus.PENDING)
        .where(PlatereadSpec.start_after < start_after)
        .where(AcquisitionPlan.priority == priority)
        .where(Wellplate.location == AcquisitionPlan.storage_location)
        .order_by(asc(PlatereadSpec.start_after))  # type: ignore
        .limit(1)
    )
    return session.exec(statement).first()


@task(cache_policy=NONE)
def get_next_normal_prio(session: Session):
    return get_next_task(session, datetime.now(timezone.utc), ImagingPriority.NORMAL)


@task(cache_policy=NONE)
def get_future_normal_prio(session: Session):
    return get_next_task(
        session, datetime.now(timezone.utc) + timedelta(hours=6), ImagingPriority.NORMAL
    )


@task(cache_policy=NONE)
def get_next_low_prio(session: Session):
    return get_next_task(session, datetime.now(timezone.utc), ImagingPriority.LOW)


@flow
def schedule():
    logger = get_run_logger()
    with get_db() as session:
        cancel_past_deadline(session)

        if any_platereads_running(session):
            logger.info(
                "There are running platereads; waiting to schedule new platereads"
            )
            return

        # if there is a normal prio task pending, schedule it
        if (normal_prio := get_next_normal_prio(session)) is not None:
            submit_plateread_spec(session=session, spec=normal_prio)
            name = normal_prio.acquisition_plan.acquisition.name
            logger.info(f"Scheduled normal prio plateread for acquisition{name}")
            return

        # otherwise, if a normal prio task is scheduled in the near future, stop
        if (future_normal_prio := get_future_normal_prio(session)) is not None:
            name = future_normal_prio.acquisition_plan.acquisition.name
            delta = future_normal_prio.start_after.astimezone(
                timezone.utc
            ) - datetime.now(timezone.utc)
            logger.info(
                f"Normal prio plateread for acquisition {name} is scheduled to run in {delta}; not enough slack time to schedule low prio platereads. Waiting for next normal prio plateread."
            )
            return

        # else, try to schedule a low prio task:
        if (low_prio := get_next_low_prio(session)) is not None:
            submit_plateread_spec(session=session, spec=low_prio)
            name = low_prio.acquisition_plan.acquisition.name
            logger.info(f"Scheduled low prio plateread for acquisition {name}")
            return


def get_deployments():
    return [schedule.to_deployment(name="scheduler", cron="*/5 * * * *")]
