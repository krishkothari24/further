"""Conservative transcript date/time normalization against an injected local clock."""

import re
from datetime import date, datetime, timedelta

from pydantic import BaseModel


WEEKDAYS = {
    name: index
    for index, name in enumerate(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    )
}


class TimeResolution(BaseModel):
    date: str | None = None
    time: str | None = None
    ambiguous: bool = False
    reason: str | None = None


def normalize_datetime(text: str, now_local: datetime) -> TimeResolution:
    """Resolve explicit dates and common weekdays; ask about ASR-like ambiguity."""

    lowered = text.lower()
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lowered)
    day: date | None = None
    if iso:
        try:
            day = date.fromisoformat(iso.group(1))
        except ValueError:
            return TimeResolution(ambiguous=True, reason="invalid_date")
    else:
        weekday = re.search(
            r"\b(?:(next|this)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            lowered,
        )
        if weekday:
            offset = (WEEKDAYS[weekday.group(2)] - now_local.weekday()) % 7
            if weekday.group(1) == "next" and offset == 0:
                offset = 7
            day = now_local.date() + timedelta(days=offset)
        elif re.search(r"\b(thirs\s*day|thur\s*day|tues\s*day)\b", lowered):
            return TimeResolution(ambiguous=True, reason="unclear_day")

    twelve_hour = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lowered)
    clock24 = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", lowered)
    hour: int | None = None
    minute = 0
    if twelve_hour:
        hour = int(twelve_hour.group(1))
        minute = int(twelve_hour.group(2) or 0)
        if hour < 1 or hour > 12 or minute > 59:
            return TimeResolution(
                date=day.isoformat() if day else None,
                ambiguous=True,
                reason="invalid_time",
            )
        hour = hour % 12 + (12 if twelve_hour.group(3) == "pm" else 0)
    elif clock24:
        hour, minute = int(clock24.group(1)), int(clock24.group(2))
    elif re.search(r"\bat\s+(?:too|two|to|\d{1,2})\b", lowered):
        return TimeResolution(
            date=day.isoformat() if day else None, ambiguous=True, reason="unclear_time"
        )

    return TimeResolution(
        date=day.isoformat() if day else None,
        time=f"{hour:02}:{minute:02}" if hour is not None else None,
    )


def spoken_slot(date_text: str, time_text: str) -> str:
    day = date.fromisoformat(date_text)
    hour = int(time_text[:2])
    minute = int(time_text[3:])
    spoken_hour = hour % 12 or 12
    spoken_time = f"{spoken_hour}" if minute == 0 else f"{spoken_hour}:{minute:02}"
    return f"{day.strftime('%A, %B')} {day.day} at {spoken_time} {'a.m.' if hour < 12 else 'p.m.'}"
