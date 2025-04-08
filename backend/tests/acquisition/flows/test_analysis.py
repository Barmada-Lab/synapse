import random
from unittest.mock import patch

from globus_compute_sdk import ShellResult
from sqlmodel import Session

from app.acquisition import crud
from app.acquisition.flows.acquisition_planning import (
    check_to_schedule_acquisition_plan,
)
from app.acquisition.flows.analysis import (
    handle_analyses,
    handle_end_of_run_analyses,
    handle_immediate_analyses,
    handle_post_read_analyses,
)
from app.acquisition.models import (
    AnalysisTrigger,
    ArtifactType,
    Repository,
    SBatchJobCreate,
    SlurmJobState,
)
from tests.acquisition.utils import (
    complete_reads,
    create_random_acquisition,
    create_random_acquisition_plan,
    create_random_analysis_spec,
    create_random_artifact_collection,
    move_plate_to_acquisition_plan_location,
)


def _mock_batch_job_submission(mock_executor_constructor):
    """Helper function to mock a batch job submission response.
    Args:
        mock_executor: The mocked executor object from unittest.mock.patch
    Returns:
        int: The randomly generated job ID that was used in the mock
    """
    job_id = random.randint(1, 1000000)
    mock_executor_constructor.return_value.__enter__.return_value.submit.return_value.result.return_value = ShellResult(
        cmd="", stderr="", returncode=0, stdout=f"Submitted batch job {job_id}"
    )


def _assert_batch_job_submission(mock_executor_constructor):
    mock_executor_constructor.return_value.__enter__.return_value.submit.assert_called_once()


def _assert_batch_job_submission_not_called(mock_executor_constructor):
    mock_executor_constructor.return_value.__enter__.return_value.submit.assert_not_called()


def test_handle_analyses_when_no_acquisition_plan(db: Session):
    """Only calls immediate analyses"""
    acquisition = create_random_acquisition(session=db)
    with (
        patch(
            "app.acquisition.flows.analysis.handle_immediate_analyses"
        ) as mock_immediate,
        patch("app.acquisition.flows.analysis.handle_post_read_analyses") as mock_pr,
        patch("app.acquisition.flows.analysis.handle_end_of_run_analyses") as mock_eor,
    ):
        handle_analyses(acquisition=acquisition, session=db)
        mock_immediate.assert_called_once_with(acquisition, db)
        mock_pr.assert_not_called()
        mock_eor.assert_not_called()


def test_handle_analyses_with_unstarted_acquisition(db: Session):
    """Calls post_read and immediate analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    # There is now an acquisition plan that has not been started
    with (
        patch(
            "app.acquisition.flows.analysis.handle_immediate_analyses"
        ) as mock_immediate,
        patch("app.acquisition.flows.analysis.handle_post_read_analyses") as mock_pr,
        patch("app.acquisition.flows.analysis.handle_end_of_run_analyses") as mock_eor,
    ):
        handle_analyses(acquisition=acquisition, session=db)
        mock_immediate.assert_called_once_with(acquisition, db)
        mock_pr.assert_not_called()
        mock_eor.assert_not_called()


def test_handle_analyses_with_one_completed_read(db: Session):
    """Calls post_read and immediate analyses when one read is completed"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=2
    )
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db, n_reads=1)  # Complete one read
    with (
        patch(
            "app.acquisition.flows.analysis.handle_immediate_analyses"
        ) as mock_immediate,
        patch("app.acquisition.flows.analysis.handle_post_read_analyses") as mock_pr,
        patch("app.acquisition.flows.analysis.handle_end_of_run_analyses") as mock_eor,
    ):
        handle_analyses(acquisition=acquisition, session=db)
        mock_immediate.assert_called_once_with(acquisition, db)
        mock_pr.assert_called_once_with(
            1, acquisition, db
        )  # Expect post_read to be called
        mock_eor.assert_not_called()


def test_handle_analyses_with_complete_acquisition(db: Session):
    """Calls immediate, post_read, and end_of_run analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )

    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    with (
        patch(
            "app.acquisition.flows.analysis.handle_post_read_analyses"
        ) as mock_post_read,
        patch(
            "app.acquisition.flows.analysis.handle_end_of_run_analyses"
        ) as mock_end_of_run,
        patch(
            "app.acquisition.flows.analysis.handle_immediate_analyses"
        ) as mock_immediate,
    ):
        handle_analyses(acquisition=acquisition, session=db)
        mock_post_read.assert_called_once_with(1, acquisition, db)
        mock_end_of_run.assert_called_once_with(acquisition, db)
        mock_immediate.assert_called_once_with(acquisition, db)


def test_handle_post_read_analyses(db: Session):
    """Submits based off of # of completed reads"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    analysis = create_random_analysis_spec(
        session=db,
        acquisition=acquisition,
        analysis_trigger=AnalysisTrigger.POST_READ,
        trigger_value=1,
    )
    assert not any(analysis.jobs)
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    with patch("app.acquisition.flows.analysis.Executor") as mock_executor:
        _mock_batch_job_submission(mock_executor)
        handle_post_read_analyses(1, acquisition, db)
        _assert_batch_job_submission(mock_executor)


def test_handle_post_read_analyses_no_matching_trigger_value(db: Session):
    """Does not submit analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    analysis = create_random_analysis_spec(
        session=db,
        acquisition=acquisition,
        analysis_trigger=AnalysisTrigger.POST_READ,
        trigger_value=0,
    )
    assert not any(analysis.jobs)
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    with patch("app.acquisition.flows.analysis.Executor") as mock_executor:
        _mock_batch_job_submission(mock_executor)
        handle_post_read_analyses(1, acquisition, db)
        _assert_batch_job_submission_not_called(mock_executor)


def test_handle_end_of_run_analyses(db: Session):
    """Submits analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    analysis = create_random_analysis_spec(
        session=db,
        acquisition=acquisition,
        analysis_trigger=AnalysisTrigger.END_OF_RUN,
    )
    assert not any(analysis.jobs)
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    with patch("app.acquisition.flows.analysis.Executor") as mock_executor:
        _mock_batch_job_submission(mock_executor)
        handle_end_of_run_analyses(acquisition, db)
        _assert_batch_job_submission(mock_executor)


def test_handle_end_of_run_analyses_no_matching_trigger(db: Session):
    """Does not submit analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    analysis = create_random_analysis_spec(
        session=db,
        acquisition=acquisition,
        analysis_trigger=AnalysisTrigger.POST_READ,
        trigger_value=0,
    )
    assert not any(analysis.jobs)
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    with patch("app.acquisition.flows.analysis.Executor") as mock_executor:
        _mock_batch_job_submission(mock_executor)
        handle_end_of_run_analyses(acquisition, db)
        _assert_batch_job_submission_not_called(mock_executor)


def test_immediate_analyses(db: Session):
    """Submits analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    analysis = create_random_analysis_spec(
        session=db,
        acquisition=acquisition,
        analysis_trigger=AnalysisTrigger.IMMEDIATE,
    )
    assert not any(analysis.jobs)
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    with patch("app.acquisition.flows.analysis.Executor") as mock_executor:
        _mock_batch_job_submission(mock_executor)
        handle_immediate_analyses(acquisition, db)
        _assert_batch_job_submission(mock_executor)


def test_immediate_analyses_already_submitted(db: Session):
    """Does not submit analyses if already submitted"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    analysis = create_random_analysis_spec(
        session=db,
        acquisition=acquisition,
        analysis_trigger=AnalysisTrigger.IMMEDIATE,
    )
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    crud.create_sbatch_job(
        session=db,
        create=SBatchJobCreate(
            status=SlurmJobState.RUNNING,
            slurm_id=random.randint(1, 1000000),
            analysis_spec_id=analysis.id,
        ),
    )
    with patch("app.acquisition.flows.analysis.Executor") as mock_executor:
        _mock_batch_job_submission(mock_executor)
        handle_immediate_analyses(acquisition, db)
        _assert_batch_job_submission_not_called(mock_executor)


def test_handle_immediate_analyses_no_matching_trigger(db: Session):
    """Does not submit analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    analysis = create_random_analysis_spec(
        session=db,
        acquisition=acquisition,
        analysis_trigger=AnalysisTrigger.END_OF_RUN,
        trigger_value=0,
    )
    assert not any(analysis.jobs)
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    handle_immediate_analyses(acquisition, db)
    db.refresh(analysis)
    assert not any(analysis.jobs)


def _stup_analysis_spec(db: Session):
    """Submits analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    analysis_spec = create_random_analysis_spec(
        session=db,
        acquisition=acquisition,
        analysis_trigger=AnalysisTrigger.IMMEDIATE,
    )
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition_plan(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    with patch("app.acquisition.flows.analysis.Executor") as mock_executor:
        _mock_batch_job_submission(mock_executor)
        handle_immediate_analyses(acquisition, db)
    return analysis_spec
