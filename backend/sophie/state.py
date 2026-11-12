"""Persisted conversation state and the boundary between suggestions and outcomes."""

from typing import Any, Literal

from pydantic import Field

from .contracts import StrictModel


TaskKind = Literal[
    "book", "reschedule", "cancel", "callback", "brochure", "contact_update"
]
Stage = Literal[
    "collecting",
    "contact_readback",
    "action_readback",
    "checked",
    "completed",
    "failed",
]


class Contact(StrictModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None


class SelectedSlot(StrictModel):
    date: str
    time: str
    timezone: Literal["America/New_York"] = "America/New_York"
    checked: bool = False


class PendingTask(StrictModel):
    kind: TaskKind
    stage: Stage = "collecting"
    slot: SelectedSlot | None = None
    last_date: str | None = None
    confirmation_id: str | None = None
    best_time: str | None = None
    address: str | None = None
    last_question: str | None = None
    intent_confirmed: bool = False


class Message(StrictModel):
    role: Literal["caller", "sophie"]
    text: str


class ConversationState(StrictModel):
    sandbox_id: str
    conversation_id: str
    revision: int = 0
    messages: list[Message] = Field(default_factory=list)
    pending_task: PendingTask | None = None
    confirmed_contact: Contact = Field(default_factory=Contact)
    tentative_contact: Contact = Field(default_factory=Contact)
    contact_confirmation: dict[str, Literal["tentative", "confirmed"]] = Field(
        default_factory=dict
    )
    lead_id: str | None = None
    selected_time: SelectedSlot | None = None
    verified_tour_ids: list[str] = Field(default_factory=list)
    stage: Stage = "collecting"
    last_outcome: str | None = None


class ToolProposal(StrictModel):
    """Untrusted model output. No proposal carries business authority."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ProposedTurn(StrictModel):
    proposals: list[ToolProposal] = Field(default_factory=list)
    draft_text: str | None = None


class ValidatedToolRequest(StrictModel):
    """Application-authored service request after checking caller state."""

    name: str
    parameters: dict[str, Any]
    operation_key: str | None = None


class ActionOutcome(StrictModel):
    kind: Literal[
        "booked",
        "not_booked",
        "rescheduled",
        "not_rescheduled",
        "canceled",
        "not_canceled",
        "callback_queued",
        "brochure_queued",
        "transfer_requested",
        "lead_saved",
        "unknown_outcome",
    ]
    code: str
    verified: bool = False
    entity_id: str | None = None
    date: str | None = None
    time: str | None = None


class Event(StrictModel):
    event_id: str
    sandbox_id: str
    conversation_id: str
    turn_id: str
    timestamp: str
    stage: str
    tool_name: str | None = None
    outcome: str | None = None
    error_class: str | None = None
    entity_id: str | None = None
    redacted_params: dict[str, Any] | None = None


class TurnResult(StrictModel):
    spoken_text: str
    conversation_id: str
    turn_id: str
    action_outcomes: list[ActionOutcome] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    status: Literal["completed", "clarification_required", "error"]
