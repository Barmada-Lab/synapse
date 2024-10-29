import random

from sqlmodel import Session

from app.labware.crud import create_wellplate
from app.labware.models import WellplateCreate, WellplateType
from tests.utils import random_lower_string


def create_random_wellplate(*, session: Session):
    name = random_lower_string()
    plate_type = random.choice(list(WellplateType))
    wellplate_create = WellplateCreate(name=name, plate_type=plate_type)
    wellplate = create_wellplate(session=session, wellplate_create=wellplate_create)
    return wellplate
