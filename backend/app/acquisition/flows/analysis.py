from prefect import get_run_logger, task
from prefect.cache_policies import NONE
from prefect.events import emit_event
from sqlmodel import Session
from synapse_greatlakes.messages import RequestSubmitJob, SynapseGreatlakesMessage

from app.acquisition import crud
from app.acquisition.models import (
    Acquisition,
    AnalysisTrigger,
    ArtifactType,
    ProcessStatus,
    Repository,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecUpdate,
    SlurmJobStatus,
)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def submit_analysis_request(analysis_spec: SBatchAnalysisSpec, session: Session):
    event = SynapseGreatlakesMessage(
        resource=f"sbatch_analysis.{analysis_spec.id}",
        payload=RequestSubmitJob(
            script=analysis_spec.analysis_cmd,
            args=analysis_spec.analysis_args,
        ),
    ).to_event()
    emit_event(**event.model_dump())
    crud.update_analysis_spec(
        session=session,
        db_analysis=analysis_spec,
        update=SBatchAnalysisSpecUpdate(status=SlurmJobStatus.SUBMITTED),
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

    acquisition_data = acquisition.get_collection(
        ArtifactType.ACQUISITION_DATA, Repository.ANALYSIS_STORE
    )
    if not acquisition_data:
        raise ValueError(
            f"Acquisition {acquisition.name} has no acquisition collection in {Repository.ANALYSIS_STORE}"
        )

    analyses = [
        analysis
        for analysis in acquisition.analysis_plan.sbatch_analyses
        if analysis.trigger == AnalysisTrigger.END_OF_RUN
    ]

    for analysis in analyses:
        logger.info(
            f"Submitting end-of-run analysis {analysis} for acquisition \
                {acquisition.name}"
        )
        submit_analysis_request(analysis, session)


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

    acquisition_data = acquisition.get_collection(
        ArtifactType.ACQUISITION_DATA, Repository.ANALYSIS_STORE
    )
    if not acquisition_data:
        raise ValueError(
            f"Acquisition {acquisition.name} has no acquisition collection in {Repository.ANALYSIS_STORE}"
        )

    analyses = [
        analysis
        for analysis in acquisition.analysis_plan.sbatch_analyses
        if analysis.trigger == AnalysisTrigger.POST_READ
        and analysis.trigger_value == read_idx
    ]

    for analysis in analyses:
        logger.info(
            f"Submitting post-read analysis {analysis} for acquisition \
                {acquisition.name}"
        )
        submit_analysis_request(analysis, session)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def handle_immediate_analyses(acquisition: Acquisition, session: Session):
    logger = get_run_logger()
    if acquisition.analysis_plan is None:
        logger.info(f"No analysis plan found for acquisition {acquisition.name}")
        return

    match acquisition.instrument.instrument_type.name:
        case "PCR":
            # HACK: just ignore acquistion data check for pcr; we pull from google drive in the analysis stage
            pass
        case _:
            acquisition_data = acquisition.get_collection(
                ArtifactType.ACQUISITION_DATA, Repository.ANALYSIS_STORE
            )
            if acquisition_data is None:
                raise ValueError(
                    f"Acquisition {acquisition.name} has no acquisition collection in {Repository.ANALYSIS_STORE}"
                )

    analyses = [
        analysis
        for analysis in acquisition.analysis_plan.sbatch_analyses
        if analysis.trigger == AnalysisTrigger.IMMEDIATE
    ]

    for analysis in analyses:
        logger.info(
            f"Submitting immediate analysis {analysis} for acquisition \
                {acquisition.name}"
        )
        submit_analysis_request(analysis, session)


@task(cache_policy=NONE)  # type: ignore[arg-type]
def handle_analyses(acquisition: Acquisition, session: Session):
    """
    Handles submitting analysis plans for an acquisition, depending on the
    presence of a corresponding acquisition plan. If an acquisition plan is
    present, this function will check the progress of the acquisition plan and
    submit post-read or end-of-run analyses as necessary. If no acquisition plan
    is found, this function will check for end-of-run analyses to submit.
    """
    logger = get_run_logger()
    if not acquisition.collections_list:
        logger.info(
            f"No collections found for acquisition {acquisition.name}; skipping analysis"
        )
        return

    handle_immediate_analyses(acquisition, session)

    if acquisition.acquisition_plan:
        n_complete = sum(
            read.status == ProcessStatus.COMPLETED
            for read in acquisition.acquisition_plan.schedule
        )
        n_end_states = sum(
            read.status.is_endstate for read in acquisition.acquisition_plan.schedule
        )
        total_reads = acquisition.acquisition_plan.n_reads
        handle_post_read_analyses(n_complete, acquisition, session)
        if n_end_states == total_reads:
            handle_end_of_run_analyses(acquisition, session)
