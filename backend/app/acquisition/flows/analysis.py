import re
import shlex

from globus_compute_sdk import Executor, ShellFunction, ShellResult
from prefect import flow, get_run_logger, task
from prefect.cache_policies import NONE
from sqlmodel import Session, or_, select

from app.acquisition import crud
from app.acquisition.models import (
    Acquisition,
    AnalysisTrigger,
    ProcessStatus,
    SBatchAnalysisSpec,
    SBatchJob,
    SBatchJobCreate,
    SBatchJobUpdate,
    SlurmJobState,
)
from app.core.config import settings
from app.core.deps import get_db

JOB_SUBMIT_REGEX = r"Submitted batch job (?P<job_id>\d+)"
JOB_STATE_REGEX = r"JobState=(?P<status>\w+)"


def submit_sbatch_job(sbatch_args: list[str], executor: Executor) -> int:
    command = shlex.join(["sbatch", *sbatch_args])
    result: ShellResult = executor.submit(ShellFunction(command)).result()
    if result.returncode != 0:
        raise ValueError(
            f"Command {command} failed with return code {result.returncode}: {result.stderr}"
        )

    match = re.search(JOB_SUBMIT_REGEX, result.stdout)
    if match is None:
        raise ValueError(f"Failed to parse job ID from stdout: {result.stdout}")
    return int(match.group("job_id"))


def get_job_status(job_id: int, executor: Executor):
    command = shlex.join(["scontrol", "show", "job", str(job_id)])
    result = executor.submit(ShellFunction(command)).result()
    if result.returncode != 0:
        raise ValueError(f"Failed to query job {job_id}: {result.stderr}")

    match = re.search(JOB_STATE_REGEX, result.stdout)
    if match is None:
        raise ValueError(f"Failed to parse job state from stdout: {result.stdout}")

    return SlurmJobState(match.group("status"))


@task(cache_policy=NONE)  # type: ignore[arg-type]
def submit_sbatch_analysis(
    analysis_spec: SBatchAnalysisSpec, executor: Executor, session: Session
):
    job_id = submit_sbatch_job(
        [analysis_spec.analysis_cmd, *analysis_spec.analysis_args], executor
    )
    crud.create_sbatch_job(
        session=session,
        create=SBatchJobCreate(
            status=SlurmJobState.PENDING,
            slurm_id=job_id,
            analysis_spec_id=analysis_spec.id,
        ),
    )


@task(cache_policy=NONE)  # type: ignore[arg-type]
def handle_end_of_run_analyses(acquisition: Acquisition, session: Session):
    logger = get_run_logger()
    logger.info(f"Handling end-of-run analyses for acquisition {acquisition.name}")
    if not acquisition.analysis_plan:
        logger.info(
            f"No analysis plan found for acquisition {acquisition.name}; skipping end-of-run analyses"
        )
        return

    analyses = [
        analysis
        for analysis in acquisition.analysis_plan.sbatch_analyses
        if analysis.trigger == AnalysisTrigger.END_OF_RUN
    ]

    with Executor(endpoint_id=settings.GLOBUS_ENDPOINT_ID) as executor:
        for analysis in analyses:
            logger.info(
                f"Submitting end-of-run analysis {analysis} for acquisition \
                        {acquisition.name}"
            )
            submit_sbatch_analysis(analysis, executor, session)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def handle_post_read_analyses(
    read_idx: int, acquisition: Acquisition, session: Session
):
    logger = get_run_logger()
    logger.info(
        f"Handling post-read analyses for acquisition {acquisition.name}; read_idx: {read_idx}"
    )
    if not acquisition.analysis_plan:
        logger.info(
            f"No analysis plan found for acquisition {acquisition.name}; skipping post-read analyses"
        )
        return

    analyses = [
        analysis
        for analysis in acquisition.analysis_plan.sbatch_analyses
        if analysis.trigger == AnalysisTrigger.POST_READ
        and analysis.trigger_value == read_idx
    ]

    with Executor(endpoint_id=settings.GLOBUS_ENDPOINT_ID) as executor:
        for analysis in analyses:
            logger.info(
                f"Submitting post-read analysis {analysis} for acquisition \
                    {acquisition.name}"
            )
            submit_sbatch_analysis(analysis, executor, session)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def handle_immediate_analyses(acquisition: Acquisition, session: Session):
    logger = get_run_logger()
    if acquisition.analysis_plan is None:
        logger.info(f"No analysis plan found for acquisition {acquisition.name}")
        return

    analyses = [
        analysis
        for analysis in acquisition.analysis_plan.sbatch_analyses
        if analysis.trigger == AnalysisTrigger.IMMEDIATE and not any(analysis.jobs)
    ]

    with Executor(endpoint_id=settings.GLOBUS_ENDPOINT_ID) as executor:
        for analysis in analyses:
            logger.info(
                f"Submitting immediate analysis {analysis} for acquisition \
                    {acquisition.name}"
            )
            submit_sbatch_analysis(analysis, executor, session)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def handle_analyses(acquisition: Acquisition, session: Session):
    """
    Handles submitting analysis plans for an acquisition, depending on the
    presence of a corresponding acquisition plan. If an acquisition plan is
    present, this function will check the progress of the acquisition plan and
    submit post-read or end-of-run analyses as necessary. If no acquisition plan
    is found, this function will check for end-of-run analyses to submit.
    """

    handle_immediate_analyses(acquisition, session)

    if acquisition.acquisition_plan:
        n_complete = sum(
            read.status == ProcessStatus.COMPLETED
            for read in acquisition.acquisition_plan.reads
        )
        n_end_states = sum(
            read.status.is_endstate for read in acquisition.acquisition_plan.reads
        )
        total_reads = acquisition.acquisition_plan.n_reads
        handle_post_read_analyses(n_complete, acquisition, session)
        if n_end_states == total_reads:
            handle_end_of_run_analyses(acquisition, session)


@flow
def sync_analysis_jobs():
    with (
        get_db() as session,
        Executor(endpoint_id=settings.GLOBUS_ENDPOINT_ID) as executor,
    ):
        active_jobs = session.exec(
            select(SBatchJob).where(
                or_(
                    SBatchJob.status == SlurmJobState.PENDING,
                    SBatchJob.status == SlurmJobState.RUNNING,
                    SBatchJob.status == SlurmJobState.PREEMPTED,
                    SBatchJob.status == SlurmJobState.SUSPENDED,
                )
            )
        ).all()

        for job in active_jobs:
            status = get_job_status(job.slurm_id, executor)
            crud.update_sbatch_job(
                session=session, db_job=job, update=SBatchJobUpdate(status=status)
            )
