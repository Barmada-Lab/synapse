from datetime import datetime

from pytz import timezone  # type: ignore

from app.core.config import settings


def local_now() -> datetime:
    tz = timezone(settings.TIMEZONE)
    return datetime.now(tz)


def to_local_tz(datetime: datetime) -> datetime:
    tz = timezone(settings.TIMEZONE)
    return datetime.astimezone(tz)
