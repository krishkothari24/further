"""Typed, repaired service inputs and outputs for the nine inherited tool names."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)


class ToolResult(StrictModel):
    ok: bool
    code: str
    data: dict[str, Any] | None = None
    operation_id: str | None = None
    state_verified: bool = False
    message: str | None = None


class CheckAvailability(StrictModel):
    date: str


class BookTour(StrictModel):
    date: str
    time: str
    lead_id: str
    party_size: int = Field(default=1, ge=1, le=20)
    confirmed: Literal[True]


class RescheduleTour(StrictModel):
    confirmation_id: str
    date: str
    time: str
    confirmed: Literal[True]


class CancelTour(StrictModel):
    confirmation_id: str
    confirmed: Literal[True]


class GetCommunityInfo(StrictModel):
    topic: str
    field: str | None = None


class UpsertLead(StrictModel):
    lead_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None

    @field_validator("first_name", "last_name", "phone", "email", "notes")
    @classmethod
    def nonblank_when_present(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("provided field must not be blank")
        return value


class ScheduleCallback(StrictModel):
    lead_id: str
    best_time: str
    confirmed: Literal[True]


class TransferToHuman(StrictModel):
    reason: str
    authorized: Literal[True]


class SendBrochure(StrictModel):
    lead_id: str
    address: str
    address_confirmed: Literal[True]


TOOL_INPUTS: dict[str, type[StrictModel]] = {
    "check_tour_availability": CheckAvailability,
    "book_tour": BookTour,
    "reschedule_tour": RescheduleTour,
    "cancel_tour": CancelTour,
    "get_community_info": GetCommunityInfo,
    "upsert_lead": UpsertLead,
    "schedule_callback": ScheduleCallback,
    "transfer_to_human": TransferToHuman,
    "send_brochure": SendBrochure,
}
