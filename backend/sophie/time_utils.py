"""Spoken rendering of already validated community-local tour slots."""

from datetime import date

from pydantic import BaseModel


class TimeResolution(BaseModel):
    date: str | None = None
    time: str | None = None
    ambiguous: bool = False
    reason: str | None = None


def spoken_slot(date_text: str, time_text: str) -> str:
    day = date.fromisoformat(date_text)
    hour = int(time_text[:2])
    minute = int(time_text[3:])
    spoken_hour = hour % 12 or 12
    spoken_time = f"{spoken_hour}" if minute == 0 else f"{spoken_hour}:{minute:02}"
    return f"{day.strftime('%A, %B')} {day.day} at {spoken_time} {'a.m.' if hour < 12 else 'p.m.'}"
