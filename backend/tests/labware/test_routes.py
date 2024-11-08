from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.labware import crud
from app.labware.models import Location, WellplateCreate, WellplateRecord, WellplateType
from tests.labware.utils import create_random_wellplate
from tests.utils import random_lower_string


def test_retrieve_wellplates(authenticated_client: TestClient, db: Session) -> None:
    # create a wellplate
    name = random_lower_string(9)
    plate_type = WellplateType.REVVITY_PHENOPLATE_96
    wellplate_in = WellplateCreate(name=name, plate_type=plate_type)
    crud.create_wellplate(session=db, wellplate_create=wellplate_in)

    response = authenticated_client.get(f"{settings.API_V1_STR}/labware/")
    assert response.status_code == status.HTTP_200_OK
    all_wellplates = response.json()

    assert all_wellplates["count"] >= 1
    for item in all_wellplates["data"]:
        WellplateRecord.model_validate(item)


def test_get_wellplate_by_name_not_found(authenticated_client: TestClient) -> None:
    name = random_lower_string(9)
    response = authenticated_client.get(
        f"{settings.API_V1_STR}/labware", params={"name": name}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] == 0
    assert response.json()["data"] == []


def test_create_wellplate(authenticated_client: TestClient, db: Session) -> None:
    name = random_lower_string(9)
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


def test_create_wellplate_empty_name(authenticated_client: TestClient) -> None:
    name = ""
    response = authenticated_client.post(
        f"{settings.API_V1_STR}/labware/",
        json={"name": name, "plate_type": WellplateType.REVVITY_PHENOPLATE_96.value},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_wellplate_long_name(authenticated_client: TestClient) -> None:
    name = random_lower_string(10)
    response = authenticated_client.post(
        f"{settings.API_V1_STR}/labware/",
        json={"name": name, "plate_type": WellplateType.REVVITY_PHENOPLATE_96.value},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_wellplate_duplicate_fails(
    authenticated_client: TestClient, db: Session
) -> None:
    name = random_lower_string(9)
    plate_type = WellplateType.REVVITY_PHENOPLATE_96
    wellplate_in = WellplateCreate(name=name, plate_type=plate_type)
    crud.create_wellplate(session=db, wellplate_create=wellplate_in)

    response = authenticated_client.post(
        f"{settings.API_V1_STR}/labware/",
        json={"name": name, "plate_type": plate_type.value},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "A wellplate with this name already exists."}


def test_update_wellplate(authenticated_client: TestClient, db: Session) -> None:
    name = random_lower_string(9)
    plate_type = WellplateType.REVVITY_PHENOPLATE_96
    wellplate_in = WellplateCreate(name=name, plate_type=plate_type)
    wellplate = crud.create_wellplate(session=db, wellplate_create=wellplate_in)

    location = Location.CQ1
    response = authenticated_client.patch(
        f"{settings.API_V1_STR}/labware/{wellplate.id}",
        json={"location": location.value},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["location"] == location.value

    db.refresh(wellplate)
    assert wellplate.location == location


def test_update_wellplate_not_found(authenticated_client: TestClient) -> None:
    location = Location.CQ1
    response = authenticated_client.patch(
        f"{settings.API_V1_STR}/labware/{2**16}",
        json={"location": location.value},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Wellplate not found."}


def test_update_wellplate_emit_event(
    authenticated_client: TestClient, db: Session
) -> None:
    wellplate_in = create_random_wellplate(session=db)
    with patch("app.labware.utils.emit_event") as mock_emit_event:
        authenticated_client.patch(
            f"{settings.API_V1_STR}/labware/{wellplate_in.id}",
            json={"location": Location.CQ1.value},
        )
        mock_emit_event.assert_called_once_with(
            "wellplate.location_update",
            resource={
                "prefect.resource.id": f"wellplate.{wellplate_in.name}",
                "location.before": Location.EXTERNAL.value,
                "location.after": Location.CQ1.value,
            },
        )


def test_update_wellplate_no_change_doesnt_emit_event(
    authenticated_client: TestClient, db: Session
) -> None:
    wellplate_in = create_random_wellplate(session=db)
    with patch("app.labware.utils.emit_event") as mock_emit_event:
        authenticated_client.patch(
            f"{settings.API_V1_STR}/labware/{wellplate_in.id}",
            json={"location": Location.EXTERNAL.value},
        )
        mock_emit_event.assert_not_called()


def test_retrieve_wellplates_unauthenticated_fails(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get(f"{settings.API_V1_STR}/labware/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Not authenticated"}


def test_create_wellplate_unauthenticated_fails(
    unauthenticated_client: TestClient,
) -> None:
    name = random_lower_string(9)
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
    name = random_lower_string(9)
    location = Location.CQ1
    response = unauthenticated_client.patch(
        f"{settings.API_V1_STR}/labware/{name}",
        json={"location": location.value},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Not authenticated"}