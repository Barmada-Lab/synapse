from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.labware import crud
from app.labware.models import Location, WellplateCreate, WellplateRecord, WellplateType
from tests.utils import random_lower_string


def test_read_wellplates(authenticated_client: TestClient, db: Session) -> None:
    # create a wellplate
    name = random_lower_string()
    plate_type = WellplateType.REVVITY_PHENOPLATE_96
    wellplate_in = WellplateCreate(name=name, plate_type=plate_type)
    crud.create_wellplate(session=db, wellplate_create=wellplate_in)

    response = authenticated_client.get(f"{settings.API_V1_STR}/labware/")
    assert response.status_code == status.HTTP_200_OK
    all_wellplates = response.json()

    assert all_wellplates["count"] >= 1
    for item in all_wellplates["data"]:
        WellplateRecord.model_validate(item)


def test_create_wellplate(authenticated_client: TestClient, db: Session) -> None:
    name = random_lower_string()
    plate_type = WellplateType.REVVITY_PHENOPLATE_96.value

    response = authenticated_client.post(
        f"{settings.API_V1_STR}/labware/",
        json={"name": name, "plate_type": plate_type},
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    assert data["name"] == name
    assert data["plate_type"] == plate_type

    # a corresponding record should appear in the database
    wellplate = crud.get_wellplate_by_name(session=db, name=name)
    assert wellplate is not None
    assert wellplate.name == name
    assert wellplate.plate_type == WellplateType.REVVITY_PHENOPLATE_96


def test_update_wellplate(authenticated_client: TestClient, db: Session) -> None:
    name = random_lower_string()
    plate_type = WellplateType.REVVITY_PHENOPLATE_96
    wellplate_in = WellplateCreate(name=name, plate_type=plate_type)
    wellplate = crud.create_wellplate(session=db, wellplate_create=wellplate_in)

    assert wellplate.location is None
    last_last_update = wellplate.last_update

    location = Location.CQ1
    response = authenticated_client.patch(
        f"{settings.API_V1_STR}/labware/{name}",
        json={"location": location.value},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["location"] == location.value

    db.refresh(wellplate)
    assert wellplate.location == location
    assert wellplate.last_update > last_last_update


def test_retrieve_wellplates_unauthenticated_fails(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get(f"{settings.API_V1_STR}/labware/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Not authenticated"}


def test_create_wellplate_unauthenticated_fails(
    unauthenticated_client: TestClient,
) -> None:
    name = random_lower_string()
    plate_type = WellplateType.REVVITY_PHENOPLATE_96.value

    response = unauthenticated_client.post(
        f"{settings.API_V1_STR}/labware/",
        json={"name": name, "plate_type": plate_type},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Not authenticated"}


def test_update_wellplate_authenticated_fails(
    unauthenticated_client: TestClient,
) -> None:
    name = random_lower_string()
    location = Location.CQ1
    response = unauthenticated_client.patch(
        f"{settings.API_V1_STR}/labware/{name}",
        json={"location": location.value},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Not authenticated"}
