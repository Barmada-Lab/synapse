from unittest.mock import patch

from sqlmodel import Session

from app.acquisition.flows.acquisition_scheduling import check_to_schedule_acquisition
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
    SlurmJobStatus,
)
from tests.acquisition.utils import (
    complete_reads,
    create_random_acquisition,
    create_random_acquisition_plan,
    create_random_analysis_spec,
    create_random_artifact_collection,
    move_plate_to_acquisition_plan_location,
)


def test_handle_analyses_no_acquisition_plan(db: Session):
    """Only calls immediate analyses"""
    acquisition = create_random_acquisition(session=db)
    create_random_artifact_collection(session=db, acquisition=acquisition)
    with patch(
        "app.acquisition.flows.analysis.handle_immediate_analyses"
    ) as mock_immediate:
        handle_analyses(acquisition=acquisition, session=db)
        mock_immediate.assert_called_once_with(acquisition, db)


def test_handle_analyses_with_incomplete_acquisition(db: Session):
    """Calls post_read and immediate analyses"""
    acquisition = create_random_acquisition(session=db)
    create_random_artifact_collection(session=db, acquisition=acquisition)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    check_to_schedule_acquisition(wellplate_id=acquisition_plan.wellplate_id)
    with (
        patch(
            "app.acquisition.flows.analysis.handle_immediate_analyses"
        ) as mock_immediate,
        patch("app.acquisition.flows.analysis.handle_post_read_analyses") as mock_pr,
    ):
        handle_analyses(acquisition=acquisition, session=db)
        mock_immediate.assert_called_once_with(acquisition, db)
        mock_pr.assert_called_once_with(0, acquisition, db)


def test_handle_analyses_with_complete_acquisition(db: Session):
    """Calls immediate, post_read, and end_of_run analyses"""
    acquisition = create_random_acquisition(session=db)
    acquisition_plan = create_random_acquisition_plan(
        session=db, acquisition=acquisition, n_reads=1
    )
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )

    check_to_schedule_acquisition(wellplate_id=acquisition_plan.wellplate_id)
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
    assert analysis.status == SlurmJobStatus.UNSUBMITTED
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    handle_post_read_analyses(1, acquisition, db)
    db.refresh(analysis)
    assert analysis.status == SlurmJobStatus.SUBMITTED


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
    assert analysis.status == SlurmJobStatus.UNSUBMITTED
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    handle_post_read_analyses(1, acquisition, db)
    db.refresh(analysis)
    assert analysis.status == SlurmJobStatus.UNSUBMITTED


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
    assert analysis.status == SlurmJobStatus.UNSUBMITTED
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    handle_end_of_run_analyses(acquisition, db)
    db.refresh(analysis)
    assert analysis.status == SlurmJobStatus.SUBMITTED


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
    assert analysis.status == SlurmJobStatus.UNSUBMITTED
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    handle_end_of_run_analyses(acquisition, db)
    db.refresh(analysis)
    assert analysis.status == SlurmJobStatus.UNSUBMITTED


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
    assert analysis.status == SlurmJobStatus.UNSUBMITTED
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    handle_immediate_analyses(acquisition, db)
    db.refresh(analysis)
    assert analysis.status == SlurmJobStatus.SUBMITTED


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
    assert analysis.status == SlurmJobStatus.UNSUBMITTED
    move_plate_to_acquisition_plan_location(
        acquisition_plan.wellplate, acquisition_plan, db
    )
    check_to_schedule_acquisition(wellplate_id=acquisition_plan.wellplate_id)
    complete_reads(acquisition_plan, db)
    create_random_artifact_collection(
        session=db,
        artifact_type=ArtifactType.ACQUISITION_DATA,
        location=Repository.ANALYSIS_STORE,
        acquisition=acquisition,
    )
    handle_immediate_analyses(acquisition, db)
    db.refresh(analysis)
    assert analysis.status == SlurmJobStatus.UNSUBMITTED
