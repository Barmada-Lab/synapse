from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.acquisition.crud import schedule_plan
from app.acquisition.models import (
    AcquisitionPlan,
    AcquisitionPlanCreate,
)
from app.core.config import settings
from app.labware.models import Location
from tests.acquisition.utils import (
    create_random_acquisition,
    create_random_acquisition_plan,
)
from tests.labware.events import create_random_wellplate
from tests.utils import random_lower_string


def test_create_plan(pw_authenticated_client: TestClient, db: Session) -> None:
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
        f"{settings.API_V1_STR}/acquisition/plans/",
        json=json,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    # a corresponding record should appear in the database
    plan = db.get(AcquisitionPlan, data["id"])
    assert plan is not None


def test_create_plan_duplicate_returns_400(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    plan_a = create_random_acquisition_plan(session=db)
    response = pw_authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition/plans/",
        json=plan_a.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "Acquisition already has an acquisition plan."


def test_create_plan_invalid_wellplate_id(
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
        f"{settings.API_V1_STR}/acquisition/plans/",
        json=json,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"] == "No corresponding wellplate found."


def test_create_plan_invalid_acquisition_id(
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
        f"{settings.API_V1_STR}/acquisition/plans/",
        json=json,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"] == "No corresponding acquisition found."


def test_delete_plan_by_id(pw_authenticated_client: TestClient, db: Session) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition/plans/{plan.id}",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # the plan should be deleted from the database
    db.reset()  # reset to session cache
    assert db.get(AcquisitionPlan, plan.id) is None


def test_delete_plan_by_id_not_found(pw_authenticated_client: TestClient) -> None:
    response = pw_authenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition/plans/{2**16}",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Plan not found"


def test_update_plateread_emit_event(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    scheduled = schedule_plan(session=db, plan=plan)
    read = scheduled.schedule[0]
    with patch("app.acquisition.routes.emit_plateread_status_update") as mock:
        response = pw_authenticated_client.patch(
            f"{settings.API_V1_STR}/acquisition/reads/{read.id}",
            json={"status": "RUNNING"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "RUNNING"
        mock.assert_called_once()


def test_update_plateread_not_found(pw_authenticated_client: TestClient) -> None:
    response = pw_authenticated_client.patch(
        f"{settings.API_V1_STR}/acquisition/reads/{2**16}",
        json={"status": "RUNNING"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Plate-read not found"


def test_update_plateread_no_change(
    pw_authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    scheduled = schedule_plan(session=db, plan=plan)
    read = scheduled.schedule[0]
    with patch("app.acquisition.routes.emit_plateread_status_update") as mock:
        response = pw_authenticated_client.patch(
            f"{settings.API_V1_STR}/acquisition/reads/{read.id}",
            json={"status": read.status.value},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == read.status.value
        mock.assert_not_called()


def test_create_plan_requires_authentication(
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
        f"{settings.API_V1_STR}/acquisition/plans/",
        json=json,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_plan_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = unauthenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition/plans/{plan.id}",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_update_plateread_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    scheduled = schedule_plan(session=db, plan=plan)
    read = scheduled.schedule[0]
    response = unauthenticated_client.patch(
        f"{settings.API_V1_STR}/acquisition/reads/{read.id}",
        json={"status": "RUNNING"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
