from datetime import timedelta
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.acquisition.crud import get_acquisition_plan_by_name, schedule_plan
from app.acquisition.models import (
    AcquisitionPlanCreate,
    AcquisitionPlanRecord,
)
from app.core.config import settings
from app.labware.models import Location
from tests.acquisition.utils import create_random_acquisition_plan
from tests.labware.utils import create_random_wellplate
from tests.utils import random_lower_string


def test_list_plans(authenticated_client: TestClient, db: Session) -> None:
    _ = create_random_acquisition_plan(session=db)

    response = authenticated_client.get(f"{settings.API_V1_STR}/acquisition/plans/")
    assert response.status_code == status.HTTP_200_OK
    all_plans = response.json()

    assert all_plans["count"] >= 1
    for item in all_plans["data"]:
        AcquisitionPlanRecord.model_validate(item)


def test_query_plan_by_name(authenticated_client: TestClient, db: Session) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = authenticated_client.get(
        f"{settings.API_V1_STR}/acquisition/plans",
        params={"name": plan.name},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert len(data) == 1
    assert response.json()["count"] == 1
    assert data[0]["name"] == plan.name


def test_get_plan_by_name_not_found(authenticated_client: TestClient) -> None:
    response = authenticated_client.get(
        f"{settings.API_V1_STR}/acquisition/plans/",
        params={"name": random_lower_string()},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] == 0
    assert response.json()["data"] == []


def test_create_plan(authenticated_client: TestClient, db: Session) -> None:
    wellplate = create_random_wellplate(session=db)
    json = AcquisitionPlanCreate(
        name=random_lower_string(),
        wellplate_id=wellplate.id,
        storage_location=Location.CQ1,
        protocol_name=random_lower_string(),
        n_reads=1,
    ).model_dump(mode="json")
    response = authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition/plans/",
        json=json,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    # a corresponding record should appear in the database
    plan = get_acquisition_plan_by_name(session=db, name=data["name"])
    assert plan is not None


def test_create_plan_duplicate_returns_400(
    authenticated_client: TestClient, db: Session
) -> None:
    plan_a = create_random_acquisition_plan(session=db)
    response = authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition/plans/",
        json=plan_a.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "A plan with this name already exists."


def test_delete_plan_by_id(authenticated_client: TestClient, db: Session) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = authenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition/plans/{plan.id}",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # the plan should be deleted from the database
    assert get_acquisition_plan_by_name(session=db, name=plan.name) is None


def test_delete_plan_by_id_not_found(authenticated_client: TestClient) -> None:
    response = authenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition/plans/{2**16}",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Plan not found"


def test_schedule_acquisition_plan(
    authenticated_client: TestClient, db: Session
) -> None:
    interval = timedelta(minutes=10)
    deadline_delta = timedelta(minutes=5)
    plan = create_random_acquisition_plan(
        session=db,
        n_reads=2,
        interval=interval,
        deadline_delta=deadline_delta,
    )
    response = authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition/plans/{plan.id}/schedule",
    )
    assert response.status_code == status.HTTP_200_OK
    record = AcquisitionPlanRecord.model_validate(response.json())
    assert len(record.schedule) == 2


def test_scheduling_a_plan_twice_returns_400(
    authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    _ = authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition/plans/{plan.id}/schedule",
    )
    response = authenticated_client.post(
        f"{settings.API_V1_STR}/acquisition/plans/{plan.id}/schedule",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "This plan has already been scheduled"


def test_update_plateread_emit_event(
    authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    scheduled = schedule_plan(session=db, plan=plan)
    read = scheduled.schedule[0]
    with patch("app.acquisition.routes.emit_plateread_status_update") as mock:
        response = authenticated_client.patch(
            f"{settings.API_V1_STR}/acquisition/reads/{read.id}",
            json={"status": "RUNNING"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "RUNNING"
        mock.assert_called_once()


def test_update_plateread_not_found(authenticated_client: TestClient) -> None:
    response = authenticated_client.patch(
        f"{settings.API_V1_STR}/acquisition/reads/{2**16}",
        json={"status": "RUNNING"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Plate-read not found"


def test_update_plateread_no_change(
    authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    scheduled = schedule_plan(session=db, plan=plan)
    read = scheduled.schedule[0]
    with patch("app.acquisition.routes.emit_plateread_status_update") as mock:
        response = authenticated_client.patch(
            f"{settings.API_V1_STR}/acquisition/reads/{read.id}",
            json={"status": read.status.value},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == read.status.value
        mock.assert_not_called()


def test_list_plans_requires_authentication(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get(f"{settings.API_V1_STR}/acquisition/plans/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_plan_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    wellplate = create_random_wellplate(session=db)
    json = AcquisitionPlanCreate(
        name=random_lower_string(),
        wellplate_id=wellplate.id,
        storage_location=Location.CQ1,
        protocol_name=random_lower_string(),
        n_reads=1,
    ).model_dump(mode="json")
    response = unauthenticated_client.post(
        f"{settings.API_V1_STR}/acquisition/plans/",
        json=json,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_schedule_acquisition_plan_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = unauthenticated_client.post(
        f"{settings.API_V1_STR}/acquisition/plans/{plan.id}/schedule",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_plan_by_name_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = unauthenticated_client.delete(
        f"{settings.API_V1_STR}/acquisition/plans/{plan.name}",
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
