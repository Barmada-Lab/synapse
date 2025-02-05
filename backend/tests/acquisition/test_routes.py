from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.acquisition.crud import create_analysis_spec, implement_plan
from app.acquisition.models import (
    Acquisition,
    AcquisitionCreate,
    AcquisitionPlan,
    AcquisitionPlanCreate,
    AcquisitionRecord,
    AnalysisPlanCreate,
    AnalysisPlanRecord,
    AnalysisTrigger,
    InstrumentCreate,
    InstrumentList,
    InstrumentRecord,
    InstrumentTypeCreate,
    InstrumentTypeList,
    InstrumentTypeRecord,
    SBatchAnalysisSpec,
    SBatchAnalysisSpecCreate,
    SBatchAnalysisSpecUpdate,
    SlurmJobStatus,
)
from app.core.config import settings
from app.labware.models import Location
from tests.acquisition.utils import (
    create_random_acquisition,
    create_random_acquisition_plan,
    create_random_analysis_plan,
    create_random_analysis_spec,
    create_random_instrument,
    create_random_instrument_type,
)
from tests.labware.events import create_random_wellplate
from tests.utils import random_lower_string


def test_create_instrument_type(pw_authenticated_client: TestClient) -> None:
    instrument_type_create = InstrumentTypeCreate(name=random_lower_string())
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/instrument_types",
        json=instrument_type_create.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert InstrumentTypeRecord.model_validate(response.json())


def test_get_instrument_types(pw_authenticated_client: TestClient) -> None:
    instrument_type_create = InstrumentTypeCreate(name=random_lower_string())
    pw_authenticated_client.post(
        f"{settings.API_V1_STR}/instrument_types",
        json=instrument_type_create.model_dump(mode="json"),
    )
    response = pw_authenticated_client.get(f"{settings.API_V1_STR}/instrument_types")
    assert response.status_code == status.HTTP_200_OK
    assert InstrumentTypeList.model_validate(response.json())
    assert any(
        item["name"] == instrument_type_create.name for item in response.json()["data"]
    )


def test_delete_instrument_type(pw_authenticated_client: TestClient) -> None:
    instrument_type_create = InstrumentTypeCreate(name=random_lower_string())
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/instrument_types",
        json=instrument_type_create.model_dump(mode="json"),
    )
    instrument_type = InstrumentTypeRecord.model_validate(response.json())
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/instrument_types/{instrument_type.id}",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    response = pw_authenticated_client.get(f"{settings.API_V1_STR}/instrument_types")
    assert response.status_code == status.HTTP_200_OK
    assert InstrumentTypeList.model_validate(response.json())
    assert instrument_type.id not in [item["id"] for item in response.json()["data"]]


def test_create_instrument(pw_authenticated_client: TestClient, db: Session) -> None:
    instrument_type = create_random_instrument_type(session=db)
    instrument_create = InstrumentCreate(
        name=random_lower_string(), instrument_type_id=instrument_type.id
    )
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/instruments",
        json=instrument_create.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert InstrumentRecord.model_validate(response.json())


def test_list_instruments(pw_authenticated_client: TestClient, db: Session) -> None:
    instrument_type = create_random_instrument_type(session=db)
    instrument_create = InstrumentCreate(
        name=random_lower_string(), instrument_type_id=instrument_type.id
    )
    pw_authenticated_client.post(
        f"{settings.API_V1_STR}/instruments",
        json=instrument_create.model_dump(mode="json"),
    )
    response = pw_authenticated_client.get(f"{settings.API_V1_STR}/instruments")
    assert response.status_code == status.HTTP_200_OK
    assert InstrumentList.model_validate(response.json())
    assert any(
        item["name"] == instrument_create.name for item in response.json()["data"]
    )


def test_delete_instrument(pw_authenticated_client: TestClient, db: Session) -> None:
    # FLAKY
    instrument_type = create_random_instrument_type(session=db)
    instrument_create = InstrumentCreate(
        name=random_lower_string(), instrument_type_id=instrument_type.id
    )
    pw_authenticated_client.post(
        f"{settings.API_V1_STR}/instruments",
        json=instrument_create.model_dump(mode="json"),
    )
    instrument = InstrumentRecord.model_validate(
        pw_authenticated_client.get(f"{settings.API_V1_STR}/instruments").json()[
            "data"
        ][0]
    )
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/instruments/{instrument.id}"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    response = pw_authenticated_client.get(f"{settings.API_V1_STR}/instruments")
    assert response.status_code == status.HTTP_200_OK
    assert InstrumentList.model_validate(response.json())
    assert instrument.id not in [item["id"] for item in response.json()["data"]]


def test_get_acquisitions(pw_authenticated_client: TestClient, db: Session) -> None:
    create_random_acquisition(session=db)
    response = pw_authenticated_client.get(f"{settings.API_V1_STR}/acquisitions/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["count"] >= 1
    assert all(
        AcquisitionRecord.model_validate(acquisition) for acquisition in data["data"]
    )


def test_get_acquisitions_requires_authentication(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get(f"{settings.API_V1_STR}/acquisitions/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_acquisition(pw_authenticated_client: TestClient, db: Session) -> None:
    instrument = create_random_instrument(session=db)
    acquisition_create = AcquisitionCreate(
        name=random_lower_string(), instrument_id=instrument.id
    )
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisitions/",
        json=acquisition_create.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_201_CREATED


def test_create_acquisition_invalid_instrument_id(
    pw_authenticated_client: TestClient,
) -> None:
    acquisition_create = AcquisitionCreate(
        name=random_lower_string(), instrument_id=2**16
    )
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisitions/",
        json=acquisition_create.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"] == "No corresponding instrument found."


def test_create_duplicate_acquisition_returns_409(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    instrument = create_random_instrument(session=db)
    acquisition_create = AcquisitionCreate(
        name=random_lower_string(), instrument_id=instrument.id
    )
    _ = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisitions/",
        json=acquisition_create.model_dump(mode="json"),
    )
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisitions/",
        json=acquisition_create.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_409_CONFLICT


def test_create_acquisition_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    instrument = create_random_instrument(session=db)
    acquisition_create = AcquisitionCreate(
        name=random_lower_string(), instrument_id=instrument.id
    )
    response = unauthenticated_client.post(
        f"{settings.API_V1_STR}/acquisitions/",
        json=acquisition_create.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_acquisition(pw_authenticated_client: TestClient, db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/acquisitions/{acquisition.id}",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # the acquisition should be deleted from the database
    db.reset()  # reset to session cache
    assert db.get(Acquisition, acquisition.id) is None


def test_delete_acquisition_not_found(pw_authenticated_client: TestClient) -> None:
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/acquisitions/{2**16}",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Acquisition not found."


def test_create_analysis_plan(pw_authenticated_client: TestClient, db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    json = AnalysisPlanCreate(acquisition_id=acquisition.id)
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/analysis_plans",
        json=json.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_201_CREATED


def test_create_analysis_plan_duplicate_returns_409(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    acquisition = create_random_acquisition(session=db)
    json = AnalysisPlanCreate(acquisition_id=acquisition.id)
    _ = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/analysis_plans",
        json=json.model_dump(mode="json"),
    )
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/analysis_plans",
        json=json.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "Acquisition already has an analysis plan."


def test_get_analysis_plan(pw_authenticated_client: TestClient, db: Session) -> None:
    acquisition = create_random_acquisition(session=db)
    json = AnalysisPlanCreate(acquisition_id=acquisition.id)
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/analysis_plans",
        json=json.model_dump(mode="json"),
    )
    plan = AnalysisPlanRecord.model_validate(response.json())
    response = pw_authenticated_client.get(
        f"{settings.API_V1_STR}/analysis_plans/{plan.id}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert AnalysisPlanRecord.model_validate(response.json())


def test_create_analysis_plan_invalid_acquisition_id(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    instrument = create_random_instrument(session=db)
    json = AnalysisPlanCreate(acquisition_id=2**16, instrument_id=instrument.id)
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/analysis_plans",
        json=json.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"] == "No corresponding acquisition found."


def test_delete_analysis_plan_by_id(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_analysis_plan(session=db)
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/analysis_plans/{plan.id}",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # the plan should be deleted from the database
    response = pw_authenticated_client.get(
        f"{settings.API_V1_STR}/analysis_plans/{plan.id}",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_analysis_plan_by_id_not_found(
    pw_authenticated_client: TestClient,
) -> None:
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/analysis_plans/{2**16}",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Analysis plan not found."


def test_create_analysis_plan_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    acquisition = create_random_acquisition(session=db)
    json = AnalysisPlanCreate(
        acquisition_id=acquisition.id, instrument_id=acquisition.instrument.id
    )
    response = unauthenticated_client.post(
        f"{settings.API_V1_STR}/analysis_plans",
        json=json.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_analysis(pw_authenticated_client: TestClient, db: Session) -> None:
    analysis_plan = create_random_analysis_plan(session=db)
    analysis = SBatchAnalysisSpecCreate(
        trigger=AnalysisTrigger.END_OF_RUN,
        analysis_cmd=random_lower_string(),
        analysis_args=[random_lower_string()],
        analysis_plan_id=analysis_plan.id,
    )
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/analyses",
        json=analysis.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_201_CREATED


def test_create_analysis_invalid_analysis_plan_id(
    pw_authenticated_client: TestClient,
) -> None:
    analysis = SBatchAnalysisSpecCreate(
        trigger=AnalysisTrigger.END_OF_RUN,
        analysis_cmd=random_lower_string(),
        analysis_args=[random_lower_string()],
        analysis_plan_id=2**16,
    )
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/analyses",
        json=analysis.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"] == "Analysis plan not found."


def test_create_analysis_requires_authentication(
    unauthenticated_client: TestClient,
) -> None:
    analysis = SBatchAnalysisSpecCreate(
        trigger=AnalysisTrigger.END_OF_RUN,
        analysis_cmd=random_lower_string(),
        analysis_args=[random_lower_string()],
        analysis_plan_id=0,
    )
    response = unauthenticated_client.post(
        f"{settings.API_V1_STR}/analyses",
        json=analysis.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_update_analysis(pw_authenticated_client: TestClient, db: Session) -> None:
    spec = create_random_analysis_spec(session=db)
    update = SBatchAnalysisSpecUpdate(status=SlurmJobStatus.COMPLETED)
    response = pw_authenticated_client.patch(
        f"{settings.API_V1_STR}/analyses/{spec.id}",
        json=update.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == SlurmJobStatus.COMPLETED.value


def test_update_analysis_not_found(pw_authenticated_client: TestClient) -> None:
    update = SBatchAnalysisSpecUpdate(status=SlurmJobStatus.COMPLETED)
    response = pw_authenticated_client.patch(
        f"{settings.API_V1_STR}/analyses/{2**16}",
        json=update.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Analysis specification not found."


def test_update_analysis_requires_authentication(
    unauthenticated_client: TestClient,
) -> None:
    update = SBatchAnalysisSpecUpdate(status=SlurmJobStatus.COMPLETED)
    response = unauthenticated_client.patch(
        f"{settings.API_V1_STR}/analyses/1",
        json=update.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_analysis(pw_authenticated_client: TestClient, db: Session) -> None:
    analysis_plan = create_random_analysis_plan(session=db)
    analysis_create = SBatchAnalysisSpecCreate(
        trigger=AnalysisTrigger.END_OF_RUN,
        analysis_cmd=random_lower_string(),
        analysis_args=[random_lower_string()],
        analysis_plan_id=analysis_plan.id,
    )
    analysis = create_analysis_spec(
        session=db,
        create=analysis_create,
    )
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/analyses/{analysis.id}",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # the plan should be deleted from the database
    db.reset()  # reset to session cache
    assert db.get(SBatchAnalysisSpec, analysis.id) is None


def test_delete_analysis_not_found(pw_authenticated_client: TestClient) -> None:
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/analyses/{2**16}",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Analysis specification not found."


def test_delete_analysis_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_analysis_plan(session=db)
    response = unauthenticated_client.delete(
        f"{settings.API_V1_STR}/analyses/{plan.id}",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_acquisition_plan(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    wellplate = create_random_wellplate(session=db)
    acquisition = create_random_acquisition(session=db)
    json = AcquisitionPlanCreate(
        wellplate_id=wellplate.id,
        acquisition_id=acquisition.id,
        storage_location=Location.CQ1,
        protocol_name=random_lower_string(),
        n_reads=1,
    ).model_dump(mode="json")
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition_plans",
        json=json,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    # a corresponding record should appear in the database
    plan = db.get(AcquisitionPlan, data["id"])
    assert plan is not None


def test_create_acquisition_plan_duplicate_returns_400(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    plan_a = create_random_acquisition_plan(session=db)
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition_plans",
        json=plan_a.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "Acquisition already has an acquisition plan."


def test_create_acquisition_plan_invalid_wellplate_id(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    acquisition = create_random_acquisition(session=db)
    json = AcquisitionPlanCreate(
        wellplate_id=2**16,
        acquisition_id=acquisition.id,
        storage_location=Location.CQ1,
        protocol_name=random_lower_string(),
        n_reads=1,
    ).model_dump(mode="json")
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition_plans",
        json=json,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"] == "No corresponding wellplate found."


def test_create_acquisition_plan_invalid_acquisition_id(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    wellplate = create_random_wellplate(session=db)
    json = AcquisitionPlanCreate(
        wellplate_id=wellplate.id,
        acquisition_id=2**16,
        storage_location=Location.CQ1,
        protocol_name=random_lower_string(),
        n_reads=1,
    ).model_dump(mode="json")
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition_plans",
        json=json,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"] == "No corresponding acquisition found."


def test_delete_acquisition_plan_by_id(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition_plans/{plan.id}",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # the plan should be deleted from the database
    db.reset()  # reset to session cache
    assert db.get(AcquisitionPlan, plan.id) is None


def test_delete_acquisition_plan_by_id_not_found(
    pw_authenticated_client: TestClient,
) -> None:
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition_plans/{2**16}",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Plan not found"


def test_create_acquisition_plan_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    wellplate = create_random_wellplate(session=db)
    acquisition = create_random_acquisition(session=db)
    json = AcquisitionPlanCreate(
        wellplate_id=wellplate.id,
        acquisition_id=acquisition.id,
        storage_location=Location.CQ1,
        protocol_name=random_lower_string(),
        n_reads=1,
    ).model_dump(mode="json")
    response = unauthenticated_client.post(
        f"{settings.API_V1_STR}/acquisition_plans",
        json=json,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_update_plateread_emit_event(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    scheduled = implement_plan(session=db, plan=plan)
    read = scheduled.reads[0]
    with patch("app.acquisition.routes.handle_plateread_status_update") as mock:
        response = pw_authenticated_client.patch(
            f"{settings.API_V1_STR}/platereads/{read.id}",
            json={"status": "RUNNING"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "RUNNING"
        mock.assert_called_once()


def test_update_plateread_not_found(pw_authenticated_client: TestClient) -> None:
    response = pw_authenticated_client.patch(
        f"{settings.API_V1_STR}/platereads/{2**16}",
        json={"status": "RUNNING"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Plate-read not found"


def test_update_plateread_no_change(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    scheduled = implement_plan(session=db, plan=plan)
    read = scheduled.reads[0]
    with patch("app.acquisition.routes.handle_plateread_status_update") as mock:
        response = pw_authenticated_client.patch(
            f"{settings.API_V1_STR}/platereads/{read.id}",
            json={"status": read.status.value},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == read.status.value
        mock.assert_not_called()


def test_update_plateread_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    scheduled = implement_plan(session=db, plan=plan)
    read = scheduled.reads[0]
    response = unauthenticated_client.patch(
        f"{settings.API_V1_STR}/platereads/{read.id}",
        json={"status": "RUNNING"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_plan_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = unauthenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition_plans/{plan.id}",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
