import random

from sqlmodel import Session

from app.labware.crud import create_wellplate
from app.labware.models import WellplateCreate, WellplateType
from tests.utils import random_lower_string


def create_random_wellplate(*, session: Session, **kwargs):
    kwargs.setdefault("name", random_lower_string(9))
    kwargs.setdefault("plate_type", random.choice(list(WellplateType)))
    wellplate_create = WellplateCreate(**kwargs)
    wellplate = create_wellplate(session=session, wellplate_create=wellplate_create)
    return wellplate
