from datetime import datetime

from sqlmodel import Session, select

from .models import (
    Acquisition,
    AcquisitionCreate,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    AnalysisPlan,
    ArtifactCollection,
    ArtifactCollectionCreate,
    ArtifactType,
    PlatereadSpec,
    PlatereadSpecUpdate,
    Repository,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecCreate,
    SBatchAnalysisSpecUpdate,
)


def create_acquisition(
    *, session: Session, acquisition_create: AcquisitionCreate
) -> Acquisition:
    db_obj = Acquisition.model_validate(acquisition_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_acquisition_by_name(*, session: Session, name: str) -> Acquisition | None:
    statement = select(Acquisition).where(Acquisition.name == name)
    db_obj = session.exec(statement).first()
    return db_obj


def create_artifact_collection(
    *,
    session: Session,
    artifact_collection_create: ArtifactCollectionCreate,
) -> ArtifactCollection:
    db_obj = ArtifactCollection.model_validate(artifact_collection_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_artifact_collection_by_key(
    *, session: Session, acquisition_id: int, key: tuple[Repository, ArtifactType]
) -> ArtifactCollection | None:
    statement = (
        select(ArtifactCollection)
        .where(ArtifactCollection.acquisition_id == acquisition_id)
        .where(ArtifactCollection.location == key[0])
        .where(ArtifactCollection.artifact_type == key[1])
    )
    return session.exec(statement).first()


# TODO: write tests
def create_artifact_collection_copy(
    *, session: Session, artifact_collection: ArtifactCollection, location: Repository
) -> ArtifactCollection:
    other_artifact_collections = artifact_collection.acquisition.collections_list
    if artifact_collection.location == location or any(
        other.location == location for other in other_artifact_collections
    ):
        raise ValueError("Duplicate artifact collection!")

    create = ArtifactCollectionCreate(
        location=location,
        artifact_type=artifact_collection.artifact_type,
        acquisition_id=artifact_collection.acquisition_id,
    )
    created = create_artifact_collection(
        session=session,
        artifact_collection_create=create,
    )

    return created


def create_acquisition_plan(
    *, session: Session, plan_create: AcquisitionPlanCreate
) -> AcquisitionPlan:
    acquisition_plan = AcquisitionPlan.model_validate(plan_create)
    session.add(acquisition_plan)
    session.commit()
    session.refresh(acquisition_plan)
    return acquisition_plan


def schedule_plan(*, session: Session, plan: AcquisitionPlan) -> AcquisitionPlan:
    start_time = datetime.now()
    for i in range(plan.n_reads):
        start_after = start_time + (i * plan.interval)
        deadline = None
        if plan.deadline_delta:
            deadline = start_after + plan.deadline_delta
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


def update_plateread(
    *,
    session: Session,
    db_plateread: PlatereadSpec,
    plateread_in: PlatereadSpecUpdate,
) -> PlatereadSpec:
    plateread_data = plateread_in.model_dump(exclude_unset=True)
    db_plateread.sqlmodel_update(plateread_data)
    session.add(db_plateread)
    session.commit()
    session.refresh(db_plateread)
    return db_plateread


def create_analysis_plan(*, session: Session, acquisition_id: int) -> AnalysisPlan:
    plan = AnalysisPlan(acquisition_id=acquisition_id)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def create_analysis_spec(
    *, session: Session, create: SBatchAnalysisSpecCreate
) -> SBatchAnalysisSpec:
    analysis = SBatchAnalysisSpec.model_validate(create)
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def update_analysis_spec(
    *,
    session: Session,
    db_analysis: SBatchAnalysisSpec,
    update: SBatchAnalysisSpecUpdate,
) -> SBatchAnalysisSpec:
    analysis_data = update.model_dump(exclude_unset=True)
    db_analysis.sqlmodel_update(analysis_data)
    session.add(db_analysis)
    session.commit()
    session.refresh(db_analysis)
    return db_analysis


def get_analysis_spec(
    *,
    session: Session,
    analysis_plan_id: int,
    analysis_cmd: str,
    analysis_args: list[str],
) -> SBatchAnalysisSpec | None:
    statement = (
        select(SBatchAnalysisSpec)
        .where(SBatchAnalysisSpec.analysis_plan_id == analysis_plan_id)
        .where(SBatchAnalysisSpec.analysis_cmd == analysis_cmd)
        .where(SBatchAnalysisSpec.analysis_args == analysis_args)
    )
    return session.exec(statement).first()
