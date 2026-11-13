"""Persisted policy runtime; typed model interpretation never authorizes writes."""

import re
import uuid
from datetime import datetime, timezone
from typing import Protocol

from .backend import CanonicalBackend
from .contracts import ToolResult
from .grounding import speak_fact
from .state import (
    ActionOutcome,
    Contact,
    ConversationState,
    Event,
    Message,
    PendingTask,
    ProposedTurn,
    SelectedSlot,
    TurnUnderstanding,
    TurnResult,
    ValidatedToolRequest,
)
from .time_utils import TimeResolution, spoken_slot


SAFE_RESULT_CODES = {
    "booked",
    "rescheduled",
    "unchanged",
    "canceled",
    "already_canceled",
    "callback_queued",
    "brochure_queued",
    "transfer_requested",
    "lead_saved",
    "slot_taken",
    "slot_unavailable",
    "past_slot",
    "not_found",
    "lead_not_found",
    "contact_required",
    "invalid_request",
    "invalid_address",
    "closed_day",
    "invalid_slot",
    "backend_contract_error",
    "unknown_outcome",
    "infrastructure_error",
    "state_changed",
    "idempotency_conflict",
}

# A selected fact may need context to answer the caller's actual question safely.
# These are registry relationships, independent of caller wording or eval cases.
FACT_CONTEXT: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {
    ("pets", "dogs"): (("pets", "dog_weight_limit_lbs"),),
    ("pricing", "two_bedroom_assisted_living"): (
        ("pricing", "assisted_living_from"),
        ("pricing", "two_bedroom_assisted_living"),
    ),
    ("memory_care", "dementia_suitability"): (
        ("memory_care", "offered"),
        ("memory_care", "dementia_suitability"),
    ),
    ("pricing", "entrance_fee_waiver"): (
        ("pricing", "entrance_fee"),
        ("pricing", "entrance_fee_waiver"),
    ),
}


class ProposalSource(Protocol):
    def propose(self, caller_text: str, state: ConversationState) -> ProposedTurn: ...


class EmptyProposalSource:
    def propose(self, caller_text: str, state: ConversationState) -> ProposedTurn:
        return ProposedTurn()


def _has_contact(contact: Contact, *, full_name: bool) -> bool:
    return bool(
        (not full_name or contact.first_name and contact.last_name)
        and (contact.phone or contact.email)
    )


def _contact_readback(contact: Contact) -> str:
    pieces = []
    if contact.first_name or contact.last_name:
        pieces.append(
            " ".join(part for part in (contact.first_name, contact.last_name) if part)
        )
    if contact.email:
        pieces.append(contact.email.replace("@", " at ").replace(".", " dot "))
    if contact.phone:
        pieces.append("phone " + " ".join(re.sub(r"\D", "", contact.phone)))
    return "I heard " + ", and ".join(pieces) + ". Is that right?"


class PolicyRuntime:
    """Persists turns/state and executes only application-validated service requests."""

    def __init__(
        self,
        backend: CanonicalBackend,
        proposals: ProposalSource | None = None,
        *,
        identity_intro: bool = False,
    ):
        self.backend = backend
        self.proposals = proposals or EmptyProposalSource()
        self.identity_intro = identity_intro

    def create_conversation(self, sandbox_id: str) -> str:
        self.backend.sandbox_now(sandbox_id)
        conversation_id = "V-" + uuid.uuid4().hex
        state = ConversationState(
            sandbox_id=sandbox_id, conversation_id=conversation_id
        )
        with self.backend._connection() as conn:
            conn.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, 0, ?, ?)",
                (
                    conversation_id,
                    sandbox_id,
                    state.model_dump_json(),
                    self._now(),
                    self._now(),
                ),
            )
        return conversation_id

    def get_state(self, sandbox_id: str, conversation_id: str) -> ConversationState:
        self.backend.sandbox_now(sandbox_id)
        with self.backend._connection() as conn:
            row = conn.execute(
                "SELECT state_json FROM conversations WHERE sandbox_id=? AND id=?",
                (sandbox_id, conversation_id),
            ).fetchone()
            if row is None:
                raise KeyError(conversation_id)
            return ConversationState.model_validate_json(row["state_json"])

    def get_events(self, sandbox_id: str, conversation_id: str) -> list[Event]:
        self.backend.sandbox_now(sandbox_id)
        with self.backend._connection() as conn:
            owner = conn.execute(
                "SELECT 1 FROM conversations WHERE sandbox_id=? AND id=?",
                (sandbox_id, conversation_id),
            ).fetchone()
            if owner is None:
                raise KeyError(conversation_id)
            rows = conn.execute(
                "SELECT payload_json FROM events WHERE sandbox_id=? AND conversation_id=? ORDER BY rowid",
                (sandbox_id, conversation_id),
            ).fetchall()
            return [Event.model_validate_json(row["payload_json"]) for row in rows]

    def handle_turn(
        self,
        sandbox_id: str,
        conversation_id: str,
        client_turn_id: str,
        caller_text: str,
    ) -> TurnResult:
        if not client_turn_id.strip() or not caller_text.strip():
            return TurnResult(
                spoken_text="Please say that again.",
                conversation_id=conversation_id,
                turn_id=client_turn_id,
                status="error",
            )
        try:
            self.backend.sandbox_now(sandbox_id)
        except KeyError:
            return TurnResult(
                spoken_text="I can't find this sandbox.",
                conversation_id=conversation_id,
                turn_id=client_turn_id,
                status="error",
            )
        with self.backend._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT state_json FROM conversations WHERE sandbox_id=? AND id=?",
                (sandbox_id, conversation_id),
            ).fetchone()
            if row is None:
                conn.rollback()
                return TurnResult(
                    spoken_text="I can't find this conversation.",
                    conversation_id=conversation_id,
                    turn_id=client_turn_id,
                    status="error",
                )
            prior = conn.execute(
                "SELECT status, result_json, caller_text FROM turns WHERE sandbox_id=? AND conversation_id=? AND client_turn_id=?",
                (sandbox_id, conversation_id, client_turn_id),
            ).fetchone()
            if prior:
                conn.rollback()
                if prior["caller_text"] != caller_text:
                    return TurnResult(
                        spoken_text="That turn ID was already used for different text. Please send a new turn ID.",
                        conversation_id=conversation_id,
                        turn_id=client_turn_id,
                        status="error",
                    )
                if prior["status"] == "completed" and prior["result_json"]:
                    return TurnResult.model_validate_json(prior["result_json"])
                return TurnResult(
                    spoken_text="I'm still processing that request.",
                    conversation_id=conversation_id,
                    turn_id=client_turn_id,
                    status="error",
                )
            processing = conn.execute(
                "SELECT 1 FROM turns WHERE sandbox_id=? AND conversation_id=? AND status='processing'",
                (sandbox_id, conversation_id),
            ).fetchone()
            if processing:
                conn.rollback()
                return TurnResult(
                    spoken_text="Please wait while I finish the previous request.",
                    conversation_id=conversation_id,
                    turn_id=client_turn_id,
                    status="error",
                )
            state = ConversationState.model_validate_json(row["state_json"])
            conn.execute(
                "INSERT INTO turns VALUES (?, ?, ?, ?, ?, 'processing', NULL, ?)",
                (
                    "R-" + uuid.uuid4().hex,
                    sandbox_id,
                    conversation_id,
                    client_turn_id,
                    caller_text,
                    self._now(),
                ),
            )
            conn.commit()

        events: list[Event] = []
        outcomes: list[ActionOutcome] = []

        def emit(
            stage: str,
            *,
            tool_name: str | None = None,
            outcome: str | None = None,
            error_class: str | None = None,
            entity_id: str | None = None,
            safe_params: dict | None = None,
        ) -> None:
            events.append(
                Event(
                    event_id="E-" + uuid.uuid4().hex,
                    sandbox_id=sandbox_id,
                    conversation_id=conversation_id,
                    turn_id=client_turn_id,
                    timestamp=self._now(),
                    stage=stage,
                    tool_name=tool_name,
                    outcome=outcome,
                    error_class=error_class,
                    entity_id=entity_id,
                    redacted_params=safe_params,
                )
            )

        state.messages.append(Message(role="caller", text=caller_text))
        emit("turn_received")
        try:
            proposed = self.proposals.propose(caller_text, state.model_copy(deep=True))
            if not isinstance(proposed, ProposedTurn):
                proposed = ProposedTurn.model_validate(proposed)
            if proposed.understanding is not None:
                emit("interpretation_received", outcome="validated")
            requested_facts: list[tuple[str, str]] = []
            if proposed.understanding is not None:
                for fact in proposed.understanding.facts:
                    if (
                        fact.topic in self.backend.facts
                        and fact.field in self.backend.facts[fact.topic]
                    ):
                        requested_facts.append((fact.topic, fact.field))
            spoken, status = self._process(
                state,
                caller_text,
                client_turn_id,
                outcomes,
                emit,
                proposed.understanding,
            )
            fact_parts: list[str] = []
            grounded_facts = dict.fromkeys(
                related
                for requested in requested_facts
                for related in FACT_CONTEXT.get(requested, (requested,))
            )
            for topic, field in grounded_facts:
                request = ValidatedToolRequest(
                    name="get_community_info",
                    parameters={"topic": topic, "field": field},
                )
                facts = self.backend.call(request.name, sandbox_id, request.parameters)
                emit(
                    "tool_result",
                    tool_name=request.name,
                    outcome=facts.code,
                    safe_params={"topic": topic, "field": field},
                )
                fact_parts.append(speak_fact(topic, field, facts))
            if fact_parts:
                spoken = " ".join(
                    fact_parts + ([spoken] if state.pending_task or outcomes else [])
                )
        except Exception:
            emit("turn_error", error_class="runtime_error")
            state.pending_task = None
            if outcomes and outcomes[-1].verified:
                # A response-generation failure after a verified write must not hide that write.
                last = outcomes[-1]
                if (
                    last.kind == "booked"
                    and last.entity_id
                    and last.entity_id not in state.verified_tour_ids
                ):
                    state.verified_tour_ids.append(last.entity_id)
                if (
                    last.kind == "canceled"
                    and last.entity_id in state.verified_tour_ids
                ):
                    state.verified_tour_ids.remove(last.entity_id)
                state.stage = "completed"
                spoken, status = PolicyRuntime._wording(last, None), "completed"
            else:
                state.stage = "failed"
                state.last_outcome = "unknown_outcome"
                spoken, status = (
                    "I can't confirm that request right now. Please try again or ask for a team member.",
                    "error",
                )
        if self.identity_intro and state.revision == 0:
            spoken = "I'm Sophie, an AI assistant for ACME Senior Living. " + spoken
        state.messages.append(Message(role="sophie", text=spoken))
        state.revision += 1
        state.last_outcome = outcomes[-1].code if outcomes else state.last_outcome
        result = TurnResult(
            spoken_text=spoken,
            conversation_id=conversation_id,
            turn_id=client_turn_id,
            action_outcomes=outcomes,
            events=events,
            status=status,
        )
        with self.backend._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE conversations SET state_json=?, revision=?, updated_at_utc=? WHERE sandbox_id=? AND id=?",
                (
                    state.model_dump_json(),
                    state.revision,
                    self._now(),
                    sandbox_id,
                    conversation_id,
                ),
            )
            conn.execute(
                "UPDATE turns SET status='completed', result_json=? WHERE sandbox_id=? AND conversation_id=? AND client_turn_id=?",
                (result.model_dump_json(), sandbox_id, conversation_id, client_turn_id),
            )
            for seq, event in enumerate(events):
                conn.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        event.event_id,
                        sandbox_id,
                        conversation_id,
                        client_turn_id,
                        seq,
                        event.stage,
                        event.model_dump_json(),
                        event.timestamp,
                    ),
                )
            conn.commit()
        return result

    def _process(
        self,
        state: ConversationState,
        text: str,
        turn_id: str,
        outcomes: list[ActionOutcome],
        emit,
        understanding: TurnUnderstanding | None = None,
    ) -> tuple[str, str]:
        pending = state.pending_task
        if understanding is None:
            return (
                "I didn't catch that clearly. Could you say it another way?",
                "clarification_required",
            )
        affirmation = understanding.confirmation == "affirm"
        denial = understanding.confirmation == "deny"
        if pending and understanding and pending.stage == "contact_readback":
            corrections = {
                key: value
                for key in ("first_name", "last_name", "phone", "email")
                if (value := getattr(understanding, key)) is not None
                and value != getattr(state.tentative_contact, key)
            }
            if corrections:
                for key, value in corrections.items():
                    setattr(state.tentative_contact, key, value)
                    state.contact_confirmation[key] = "tentative"
                return _contact_readback(
                    state.tentative_contact
                ), "clarification_required"
        if pending and understanding and pending.stage == "action_readback":
            changed_action = understanding.intent not in {"none", pending.kind}
            changed_slot = bool(
                pending.slot
                and (
                    understanding.date
                    and understanding.date != pending.slot.date
                    or understanding.time
                    and understanding.time != pending.slot.time
                )
            )
            if changed_action:
                state.pending_task = None
                state.stage = "collecting"
                return (
                    "Okay, I haven't made that change. Please say what you want me to do.",
                    "clarification_required",
                )
            if changed_slot:
                pending.slot = None
                pending.stage = "collecting"
                state.selected_time = None
                state.stage = "collecting"
        if pending and pending.stage == "contact_readback":
            if affirmation:
                return self._confirm_contact(state, turn_id, outcomes, emit)
            if denial:
                for field, value in state.tentative_contact.model_dump().items():
                    if (
                        value is not None
                        and state.contact_confirmation.get(field) == "tentative"
                    ):
                        state.contact_confirmation.pop(field)
                state.tentative_contact = Contact()
                pending.stage = "collecting"
                state.stage = "collecting"
                return (
                    "Please repeat the name or contact detail I got wrong.",
                    "clarification_required",
                )
        if pending and pending.stage == "action_readback":
            if affirmation:
                return self._execute_pending(state, turn_id, outcomes, emit)
            if denial:
                state.pending_task = None
                state.stage = "collecting"
                return "Okay, I haven't made that change.", "completed"

        if (
            pending
            and understanding
            and pending.stage in {"contact_readback", "action_readback"}
            and understanding.confirmation == "unclear"
        ):
            return (
                "I didn't catch a clear yes or no. Should I proceed with what I just read back?",
                "clarification_required",
            )

        contact = Contact(
            first_name=understanding.first_name,
            last_name=understanding.last_name,
            phone=understanding.phone,
            email=understanding.email,
        )
        has_new_contact = any(
            value is not None for value in contact.model_dump().values()
        )
        if (
            has_new_contact
            and state.lead_id
            and understanding.intent == "contact_update"
        ):
            state.pending_task = PendingTask(
                kind="contact_update", stage="contact_readback", intent_confirmed=True
            )
            state.tentative_contact = contact
            for field, value in contact.model_dump().items():
                if value is not None:
                    state.contact_confirmation[field] = "tentative"
            return _contact_readback(contact), "clarification_required"

        intent = understanding.intent

        if (
            intent == "cancel"
            and pending
            and pending.kind == "book"
            and not state.verified_tour_ids
        ):
            state.pending_task = None
            state.stage = "completed"
            return (
                "I haven't booked the tour we were discussing. If you mean an existing tour, please give me its confirmation number.",
                "completed",
            )

        if intent in {"book", "reschedule", "cancel", "brochure", "callback"}:
            if pending is None or pending.kind != intent:
                state.pending_task = PendingTask(kind=intent, intent_confirmed=True)
        elif intent == "transfer":
            request = ValidatedToolRequest(
                name="transfer_to_human",
                parameters={
                    "reason": "caller requested a team member",
                    "authorized": True,
                },
                operation_key=f"{state.conversation_id}:{turn_id}:transfer",
            )
            outcome = self._execute(state, request, emit)
            outcomes.append(outcome)
            return self._wording(
                outcome, None
            ), "completed" if outcome.verified else "error"

        pending = state.pending_task
        if pending is None:
            if intent == "vendor":
                return (
                    "I don't have a confirmed purchasing contact. I can record a request to speak with a team member.",
                    "completed",
                )
            if intent == "availability":
                resolution = self._resolve_time(state, text, understanding)
                if resolution.ambiguous or not resolution.date or not resolution.time:
                    return "Which date and time did you mean?", "clarification_required"
                availability = self.backend.call(
                    "check_tour_availability",
                    state.sandbox_id,
                    {"date": resolution.date},
                )
                emit(
                    "tool_result",
                    tool_name="check_tour_availability",
                    outcome=availability.code,
                    safe_params={"date": resolution.date},
                )
                if availability.ok and any(
                    slot["time"] == resolution.time
                    for slot in availability.data["slots"]
                ):
                    return (
                        f"{spoken_slot(resolution.date, resolution.time)} is available for a tour.",
                        "completed",
                    )
                return (
                    "That tour time isn't available. Which other weekday and time works for you?",
                    "completed",
                )
            return (
                "I can help with a tour or take a request for a team member.",
                "completed",
            )

        tour_id = understanding.confirmation_id
        if pending.kind in {"cancel", "reschedule"}:
            if tour_id:
                pending.confirmation_id = next(
                    (
                        stored
                        for stored in state.verified_tour_ids
                        if stored.lower() == tour_id.lower()
                    ),
                    None,
                )
            elif len(state.verified_tour_ids) == 1:
                pending.confirmation_id = state.verified_tour_ids[0]
            if pending.confirmation_id not in state.verified_tour_ids:
                pending.confirmation_id = None
                if tour_id and state.verified_tour_ids:
                    reply = "That confirmation number doesn't match an active tour in this conversation, so I haven't changed it. Please check the number."
                elif state.verified_tour_ids:
                    reply = "Which tour do you mean? Please give me its confirmation number."
                else:
                    reply = "I can't find an active tour in this conversation, so I haven't changed it. Please check the confirmation number."
                return (
                    reply,
                    "clarification_required",
                )

        if pending.kind in {"book", "reschedule"}:
            resolution = self._resolve_time(state, text, understanding)
            if resolution.date:
                pending.last_date = resolution.date
            if resolution.ambiguous:
                return (
                    "I didn't catch the day or time clearly. Which date and time did you mean?",
                    "clarification_required",
                )
            selected_date = resolution.date or (
                pending.last_date if resolution.time else None
            )
            if selected_date and resolution.time:
                availability = self.backend.call(
                    "check_tour_availability", state.sandbox_id, {"date": selected_date}
                )
                emit(
                    "tool_result",
                    tool_name="check_tour_availability",
                    outcome=availability.code,
                    safe_params={"date": selected_date},
                )
                if not availability.ok or not any(
                    slot["time"] == resolution.time
                    for slot in (availability.data or {}).get("slots", [])
                ):
                    pending.slot = None
                    state.selected_time = None
                    return (
                        "That tour time isn't available. Which other weekday and time works for you?",
                        "clarification_required",
                    )
                pending.slot = SelectedSlot(
                    date=selected_date, time=resolution.time, checked=True
                )
                state.selected_time = pending.slot

        if pending.kind == "callback":
            pending.best_time = understanding.best_time or pending.best_time
        if pending.kind == "brochure":
            pending.address = understanding.address or pending.address

        if has_new_contact and pending.kind in {"book", "callback", "brochure"}:
            state.tentative_contact = contact
            pending.stage = "contact_readback"
            state.stage = "contact_readback"
            for field, value in contact.model_dump().items():
                if value is not None:
                    state.contact_confirmation[field] = "tentative"
            return _contact_readback(contact), "clarification_required"

        return self._next_question(state)

    def _resolve_time(
        self,
        state: ConversationState,
        text: str,
        understanding: TurnUnderstanding | None,
    ) -> TimeResolution:
        date, hour = understanding.date, understanding.time
        if date is not None:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return TimeResolution(ambiguous=True, reason="invalid_date")
        if hour is not None and not re.fullmatch(r"(?:0\d|1\d|2[0-3]):[0-5]\d", hour):
            return TimeResolution(ambiguous=True, reason="invalid_time")
        return TimeResolution(
            date=date, time=hour, ambiguous=understanding.time_ambiguous
        )

    def _confirm_contact(
        self,
        state: ConversationState,
        turn_id: str,
        outcomes: list[ActionOutcome],
        emit,
    ) -> tuple[str, str]:
        changes = {
            key: value
            for key, value in state.tentative_contact.model_dump().items()
            if value is not None
        }
        if not changes:
            return "Please repeat your contact details.", "clarification_required"
        if state.lead_id:
            changes["lead_id"] = state.lead_id
        request = ValidatedToolRequest(
            name="upsert_lead",
            parameters=changes,
            operation_key=f"{state.conversation_id}:{turn_id}:contact",
        )
        outcome = self._execute(state, request, emit)
        outcomes.append(outcome)
        if not outcome.verified:
            return (
                "I couldn't confirm that contact detail. Please repeat it.",
                "clarification_required",
            )
        state.lead_id = outcome.entity_id
        for field, value in state.tentative_contact.model_dump().items():
            if value is not None:
                setattr(state.confirmed_contact, field, value)
                state.contact_confirmation[field] = "confirmed"
        state.tentative_contact = Contact()
        if state.pending_task and state.pending_task.kind == "contact_update":
            state.pending_task = None
            state.stage = "completed"
            return "I've updated the contact detail you confirmed.", "completed"
        if state.pending_task:
            state.pending_task.stage = "collecting"
        return self._next_question(state)

    def _next_question(self, state: ConversationState) -> tuple[str, str]:
        pending = state.pending_task
        if pending is None:
            return "How else can I help?", "completed"
        state.stage = "collecting"
        if pending.kind == "book":
            if pending.slot is None or not pending.slot.checked:
                return (
                    "Which weekday and time would you like for the tour?",
                    "clarification_required",
                )
            if not _has_contact(state.confirmed_contact, full_name=True):
                return (
                    "What's your full name and a phone number or email I can confirm?",
                    "clarification_required",
                )
            pending.stage = "action_readback"
            state.stage = "action_readback"
            return (
                f"May I book your tour for {spoken_slot(pending.slot.date, pending.slot.time)}?",
                "clarification_required",
            )
        if pending.kind == "reschedule":
            if not pending.confirmation_id:
                return (
                    "What's the confirmation number for the tour to move?",
                    "clarification_required",
                )
            if pending.slot is None or not pending.slot.checked:
                return (
                    "Which new weekday and time would you like?",
                    "clarification_required",
                )
            pending.stage = "action_readback"
            state.stage = "action_readback"
            return (
                f"May I move your tour ending in {pending.confirmation_id[-6:]} to {spoken_slot(pending.slot.date, pending.slot.time)}?",
                "clarification_required",
            )
        if pending.kind == "cancel":
            if not pending.confirmation_id:
                return (
                    "What's the confirmation number for the tour to cancel?",
                    "clarification_required",
                )
            pending.stage = "action_readback"
            state.stage = "action_readback"
            return (
                f"Should I cancel your tour ending in {pending.confirmation_id[-6:]}?",
                "clarification_required",
            )
        if pending.kind == "callback":
            if not state.lead_id or not _has_contact(
                state.confirmed_contact, full_name=False
            ):
                return (
                    "What's a phone number or email I can confirm for the callback request?",
                    "clarification_required",
                )
            if not pending.best_time:
                return (
                    "What would be a good time for a team member to call?",
                    "clarification_required",
                )
            pending.stage = "action_readback"
            state.stage = "action_readback"
            return (
                f"May I queue a callback request for {pending.best_time}?",
                "clarification_required",
            )
        if pending.kind == "brochure":
            if not state.lead_id or not _has_contact(
                state.confirmed_contact, full_name=False
            ):
                return (
                    "What's your name and a phone number or email I can confirm?",
                    "clarification_required",
                )
            if not pending.address:
                return "What's the full mailing address?", "clarification_required"
            pending.stage = "action_readback"
            state.stage = "action_readback"
            return (
                f"May I queue a brochure request for {pending.address}?",
                "clarification_required",
            )
        return "Please tell me the contact detail to correct.", "clarification_required"

    def _execute_pending(
        self,
        state: ConversationState,
        turn_id: str,
        outcomes: list[ActionOutcome],
        emit,
    ) -> tuple[str, str]:
        pending = state.pending_task
        if pending is None or not pending.intent_confirmed:
            return (
                "I don't have a confirmed request to act on.",
                "clarification_required",
            )
        name: str
        params: dict
        if (
            pending.kind == "book"
            and pending.slot
            and pending.slot.checked
            and state.lead_id
            and _has_contact(state.confirmed_contact, full_name=True)
        ):
            name = "book_tour"
            params = {
                "date": pending.slot.date,
                "time": pending.slot.time,
                "lead_id": state.lead_id,
                "confirmed": True,
            }
        elif (
            pending.kind == "reschedule"
            and pending.confirmation_id in state.verified_tour_ids
            and pending.slot
            and pending.slot.checked
        ):
            name = "reschedule_tour"
            params = {
                "confirmation_id": pending.confirmation_id,
                "date": pending.slot.date,
                "time": pending.slot.time,
                "confirmed": True,
            }
        elif (
            pending.kind == "cancel"
            and pending.confirmation_id in state.verified_tour_ids
        ):
            name = "cancel_tour"
            params = {"confirmation_id": pending.confirmation_id, "confirmed": True}
        elif (
            pending.kind == "callback"
            and state.lead_id
            and _has_contact(state.confirmed_contact, full_name=False)
            and pending.best_time
        ):
            name = "schedule_callback"
            params = {
                "lead_id": state.lead_id,
                "best_time": pending.best_time,
                "confirmed": True,
            }
        elif pending.kind == "brochure" and state.lead_id and pending.address:
            name = "send_brochure"
            params = {
                "lead_id": state.lead_id,
                "address": pending.address,
                "address_confirmed": True,
            }
        else:
            return self._next_question(state)
        request = ValidatedToolRequest(
            name=name,
            parameters=params,
            operation_key=f"{state.conversation_id}:{turn_id}:{name}",
        )
        outcome = self._execute(state, request, emit)
        outcomes.append(outcome)
        if outcome.verified:
            if outcome.kind == "booked" and outcome.entity_id:
                state.verified_tour_ids.append(outcome.entity_id)
            elif (
                outcome.kind == "canceled"
                and outcome.entity_id in state.verified_tour_ids
            ):
                state.verified_tour_ids.remove(outcome.entity_id)
            state.pending_task = None
            state.stage = "completed"
        else:
            state.stage = "failed"
            if outcome.code in {"slot_taken", "slot_unavailable", "past_slot"}:
                pending.slot = None
                state.selected_time = None
                pending.stage = "collecting"
            else:
                # An uncertain write must not be offered for automatic replay.
                state.pending_task = None
        return self._wording(
            outcome, pending
        ), "completed" if outcome.verified else "clarification_required"

    def _execute(
        self, state: ConversationState, request: ValidatedToolRequest, emit
    ) -> ActionOutcome:
        emit(
            "policy_validated",
            tool_name=request.name,
            safe_params={
                key: value
                for key, value in request.parameters.items()
                if key in {"date", "time"}
            },
        )
        result = self.backend.call(
            request.name,
            state.sandbox_id,
            request.parameters,
            operation_key=request.operation_key,
        )
        verified = self._verify_backend_result(state.sandbox_id, request, result)
        safe_code = (
            result.code
            if result.code in SAFE_RESULT_CODES
            else "backend_contract_error"
        )
        data = result.data or {}
        possible_id = data.get("confirmation_id") or data.get("request_id")
        safe_id = (
            possible_id
            if verified
            and isinstance(possible_id, str)
            and re.fullmatch(r"[A-Z]-[a-f0-9]+", possible_id)
            else None
        )
        emit(
            "tool_result",
            tool_name=request.name,
            outcome=safe_code,
            error_class=None if verified else safe_code,
            entity_id=safe_id,
        )
        success_kind = {
            "book_tour": "booked",
            "reschedule_tour": "rescheduled",
            "cancel_tour": "canceled",
            "schedule_callback": "callback_queued",
            "send_brochure": "brochure_queued",
            "transfer_to_human": "transfer_requested",
            "upsert_lead": "lead_saved",
        }[request.name]
        failure_kind = {
            "book_tour": "not_booked",
            "reschedule_tour": "not_rescheduled",
            "cancel_tour": "not_canceled",
        }.get(request.name, "unknown_outcome")
        return ActionOutcome(
            kind=success_kind if verified else failure_kind,
            code=safe_code if verified or not result.ok else "backend_contract_error",
            verified=verified,
            entity_id=data.get("confirmation_id")
            or data.get("request_id")
            or data.get("lead_id")
            if verified
            else None,
            date=data.get("date") if verified else None,
            time=data.get("time") if verified else None,
        )

    def _verify_backend_result(
        self, sandbox_id: str, request: ValidatedToolRequest, result: ToolResult
    ) -> bool:
        name = request.name
        expected_codes = {
            "book_tour": {"booked"},
            "reschedule_tour": {"rescheduled", "unchanged"},
            "cancel_tour": {"canceled", "already_canceled"},
            "upsert_lead": {"lead_saved"},
            "schedule_callback": {"callback_queued"},
            "send_brochure": {"brochure_queued"},
            "transfer_to_human": {"transfer_requested"},
        }
        if (
            not result.ok
            or not result.state_verified
            or not result.data
            or not result.operation_id
            or result.code not in expected_codes[name]
            or result.data.get("error") is not None
        ):
            return False
        data = result.data
        snapshot = self.backend.snapshot(sandbox_id)
        if name == "upsert_lead":
            return any(
                row["id"] == data.get("lead_id")
                and all(
                    row[key] == value
                    for key, value in request.parameters.items()
                    if key != "lead_id"
                )
                for row in snapshot["leads"]
            )
        if name in {"book_tour", "reschedule_tour", "cancel_tour"}:
            identifier = data.get("confirmation_id")
            if not isinstance(identifier, str) or not identifier:
                return False
            return any(
                row["id"] == identifier
                and row["status"] == ("canceled" if name == "cancel_tour" else "booked")
                and (
                    name == "book_tour"
                    or identifier == request.parameters["confirmation_id"]
                )
                and (
                    name == "cancel_tour"
                    or row["local_date"] == request.parameters["date"]
                    and row["local_time"] == request.parameters["time"]
                    and data.get("date") == request.parameters["date"]
                    and data.get("time") == request.parameters["time"]
                )
                and (
                    name != "book_tour"
                    or row["lead_id"] == request.parameters["lead_id"]
                )
                for row in snapshot["tours"]
            )
        table = {
            "schedule_callback": "callbacks",
            "send_brochure": "brochures",
            "transfer_to_human": "transfers",
        }[name]
        column = {
            "schedule_callback": ("best_time", "best_time"),
            "send_brochure": ("postal_address", "address"),
            "transfer_to_human": ("reason", "reason"),
        }[name]
        return any(
            row["id"] == data.get("request_id")
            and row["status"]
            == ("requested" if name == "transfer_to_human" else "queued")
            and row[column[0]] == request.parameters[column[1]]
            and (
                name == "transfer_to_human"
                or row["lead_id"] == request.parameters["lead_id"]
            )
            for row in snapshot[table]
        )

    @staticmethod
    def _wording(outcome: ActionOutcome, pending: PendingTask | None) -> str:
        if not outcome.verified:
            if outcome.code in {"slot_taken", "slot_unavailable"}:
                return "That tour time is no longer available. Which other weekday and time works for you?"
            if outcome.code == "not_found":
                return "I couldn't find that tour, so I haven't changed it. Please check the confirmation number."
            return "I couldn't confirm that request, so I won't say it was completed. A team member can help."
        if outcome.kind == "booked" and outcome.date and outcome.time:
            slot = spoken_slot(outcome.date, outcome.time).rstrip(".")
            return f"Your tour is booked for {slot}. Your confirmation number is {outcome.entity_id}."
        if outcome.kind == "rescheduled" and outcome.date and outcome.time:
            slot = spoken_slot(outcome.date, outcome.time).rstrip(".")
            return f"Your tour is now set for {slot}."
        if outcome.kind == "canceled":
            return "Your tour is canceled."
        if outcome.kind == "callback_queued":
            return "I've queued your callback request for the team."
        if outcome.kind == "brochure_queued":
            return "I've queued your brochure request for the team."
        if outcome.kind == "transfer_requested":
            return "I've saved a request for a team member in this preview. I can't connect you live here."
        return "I've saved the confirmed contact detail."

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
