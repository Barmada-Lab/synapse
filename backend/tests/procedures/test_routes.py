from datetime import timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.labware.models import Location
from app.procedures.crud import get_acquisition_plan_by_name
from app.procedures.models import (
    AcquisitionPlanCreate,
    AcquisitionPlanRecord,
)
from tests.labware.utils import create_random_wellplate
from tests.procedures.utils import create_random_acquisition_plan
from tests.utils import random_lower_string


def test_list_plans(authenticated_client: TestClient, db: Session) -> None:
    # create a plan
    _ = create_random_acquisition_plan(session=db)

    response = authenticated_client.get(f"{settings.API_V1_STR}/procedures/")
    assert response.status_code == status.HTTP_200_OK
    all_plans = response.json()

    assert all_plans["count"] >= 1
    for item in all_plans["data"]:
        AcquisitionPlanRecord.model_validate(item)


def test_query_plan_by_name(authenticated_client: TestClient, db: Session) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = authenticated_client.get(
        f"{settings.API_V1_STR}/procedures",
        params={"name": plan.name},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert len(data) == 1
    assert response.json()["count"] == 1
    assert data[0]["name"] == plan.name


def test_get_plan_by_name_not_found(authenticated_client: TestClient) -> None:
    response = authenticated_client.get(
        f"{settings.API_V1_STR}/procedures/",
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
        f"{settings.API_V1_STR}/procedures/",
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
        f"{settings.API_V1_STR}/procedures/",
        json=plan_a.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "A plan with this name already exists."


def test_delete_plan_by_id(authenticated_client: TestClient, db: Session) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = authenticated_client.delete(
        f"{settings.API_V1_STR}/procedures/{plan.id}",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # the plan should be deleted from the database
    assert get_acquisition_plan_by_name(session=db, name=plan.name) is None


def test_delete_plan_by_id_not_found(authenticated_client: TestClient) -> None:
    response = authenticated_client.delete(
        f"{settings.API_V1_STR}/procedures/{2**16}",
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
        f"{settings.API_V1_STR}/procedures/{plan.id}/schedule",
    )
    assert response.status_code == status.HTTP_200_OK
    record = AcquisitionPlanRecord.model_validate(response.json())
    assert len(record.scheduled_reads) == 2


def test_scheduling_a_plan_twice_returns_400(
    authenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    _ = authenticated_client.post(
        f"{settings.API_V1_STR}/procedures/{plan.id}/schedule",
    )
    response = authenticated_client.post(
        f"{settings.API_V1_STR}/procedures/{plan.id}/schedule",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "This plan has already been scheduled"


def test_list_plans_requires_authentication(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get(f"{settings.API_V1_STR}/procedures/")
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
        f"{settings.API_V1_STR}/procedures/",
        json=json,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_schedule_acquisition_plan_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = unauthenticated_client.post(
        f"{settings.API_V1_STR}/procedures/{plan.id}/schedule",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_plan_by_name_requires_authentication(
    unauthenticated_client: TestClient, db: Session
) -> None:
    plan = create_random_acquisition_plan(session=db)
    response = unauthenticated_client.delete(
        f"{settings.API_V1_STR}/procedures/{plan.name}",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
