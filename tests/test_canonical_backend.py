"""Deterministic M1 service tests inspect persisted effects, not spoken strings."""

import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sophie.backend import (
    CanonicalBackend,
    FixedClock,
    TestFaults,
    validate_booking_response,
)
from sophie.contracts import TOOL_INPUTS


NOW = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)  # Monday, 08:00 New York
MONDAY = "2026-11-09"
TUESDAY = "2026-11-10"
WEDNESDAY = "2026-11-11"


@pytest.fixture
def backend(tmp_path):
    service = CanonicalBackend(tmp_path / "sophie.db", clock=FixedClock(NOW))
    return service, service.create_sandbox()


def invoke(service, sandbox, tool, key=None, **params):
    return service.call(tool, sandbox, params, operation_key=key)


def lead(service, sandbox, key="lead-1", **overrides):
    params = {
        "first_name": "James",
        "last_name": "Smith",
        "email": "james@example.test",
    }
    params.update(overrides)
    result = invoke(service, sandbox, "upsert_lead", key, **params)
    assert result.ok and result.state_verified
    return result.data["lead_id"]


def book(service, sandbox, lead_id, key="booking-1", date=MONDAY, time="09:00"):
    return invoke(
        service,
        sandbox,
        "book_tour",
        key,
        date=date,
        time=time,
        lead_id=lead_id,
        confirmed=True,
    )


def test_all_nine_repaired_tool_inputs_exist():
    assert set(TOOL_INPUTS) == {
        "check_tour_availability",
        "book_tour",
        "reschedule_tour",
        "cancel_tour",
        "get_community_info",
        "upsert_lead",
        "schedule_callback",
        "transfer_to_human",
        "send_brochure",
    }


def test_facts_have_authoritative_values_and_field_provenance(backend):
    service, sandbox = backend
    pricing = invoke(service, sandbox, "get_community_info", topic="pricing")
    assert pricing.ok and pricing.state_verified
    assert pricing.data["fields"]["entrance_fee"] == {
        "value": 3500,
        "unit": "USD",
        "source": "mock-original",
        "status": "known",
    }
    assert pricing.data["fields"]["two_bedroom_assisted_living"]["status"] == "unknown"
    pets = invoke(service, sandbox, "get_community_info", topic="pets")
    assert pets.data["fields"]["dog_weight_limit_lbs"]["value"] == 30
    memory = invoke(service, sandbox, "get_community_info", topic="memory_care")
    assert memory.data["fields"]["offered"]["value"] is False
    assert (
        memory.data["fields"]["dementia_suitability"]["status"]
        == "needs_staff_confirmation"
    )
    dietary = invoke(service, sandbox, "get_community_info", topic="dietary")
    assert dietary.data["fields"]["low_sodium"]["source"] == "legacy-prompt"
    assert dietary.data["fields"]["kosher"]["status"] == "unknown"
    assert (
        invoke(service, sandbox, "get_community_info", topic="waiver").code
        == "fact_not_found"
    )
    assert (
        invoke(
            service, sandbox, "get_community_info", topic="pricing", field="fabricated"
        ).code
        == "fact_not_found"
    )


def test_every_original_mock_fact_value_is_preserved(backend):
    service, _ = backend
    source = Path(__file__).resolve().parents[1] / "inherited" / "mock_tools.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "COMMUNITY_INFO"
            for target in node.targets
        )
    )
    original = ast.literal_eval(node.value)
    for topic, value in original.items():
        if isinstance(value, dict):
            for field, original_value in value.items():
                fact = service.facts[topic][field]
                assert (
                    fact["value"] == original_value
                    and fact["source"] == "mock-original"
                )
        else:
            field = {"phone": "main", "address": "community"}.get(topic, "offered")
            fact = service.facts[topic][field]
            assert fact["value"] == value and fact["source"] == "mock-original"


def test_monday_availability_local_utc_and_calendar_rejections(backend):
    service, sandbox = backend
    monday = invoke(service, sandbox, "check_tour_availability", date=MONDAY)
    assert monday.ok and monday.state_verified
    assert monday.data["slots"][0] == {
        "date": MONDAY,
        "time": "09:00",
        "timezone": "America/New_York",
        "starts_at_utc": "2026-11-09T14:00:00+00:00",
    }
    assert monday.data["slots"][-1]["time"] == "18:00"
    tuesday = invoke(service, sandbox, "check_tour_availability", date=TUESDAY)
    assert "14:00" not in {slot["time"] for slot in tuesday.data["slots"]}
    assert (
        invoke(service, sandbox, "check_tour_availability", date="2026-11-14").code
        == "closed_day"
    )
    assert (
        invoke(service, sandbox, "check_tour_availability", date="2026-11-15").code
        == "closed_day"
    )
    assert (
        invoke(service, sandbox, "check_tour_availability", date="2026-11-08").code
        == "past_date"
    )
    assert (
        invoke(service, sandbox, "check_tour_availability", date="2026-02-30").code
        == "invalid_date"
    )


def test_summer_slot_has_daylight_offset(tmp_path):
    service = CanonicalBackend(
        tmp_path / "summer.db",
        clock=FixedClock(datetime(2026, 7, 6, 11, tzinfo=timezone.utc)),
    )
    sandbox = service.create_sandbox()
    slots = invoke(service, sandbox, "check_tour_availability", date="2026-07-06").data[
        "slots"
    ]
    assert slots[0]["starts_at_utc"] == "2026-07-06T13:00:00+00:00"


def test_booking_email_only_readback_and_duplicate_key(backend):
    service, sandbox = backend
    lead_id = lead(service, sandbox)
    first = book(service, sandbox, lead_id)
    assert first.ok and first.code == "booked" and first.state_verified
    tour = service.snapshot(sandbox)["tours"][0]
    assert tour["id"] == first.data["confirmation_id"]
    assert (
        tour["lead_id"],
        tour["local_date"],
        tour["local_time"],
        tour["status"],
    ) == (lead_id, MONDAY, "09:00", "booked")
    assert tour["starts_at_utc"] == "2026-11-09T14:00:00+00:00"
    replay = book(service, sandbox, lead_id)
    assert replay.model_dump() == first.model_dump()
    assert len(service.snapshot(sandbox)["tours"]) == 1
    changed = book(service, sandbox, lead_id, time="10:00")
    assert not changed.ok and changed.code == "idempotency_conflict"
    assert len(service.snapshot(sandbox)["tours"]) == 1


def test_no_direct_invalid_booking_or_empty_lead(backend):
    service, sandbox = backend
    assert not invoke(service, sandbox, "upsert_lead", "blank").ok
    incomplete = invoke(service, sandbox, "upsert_lead", "partial", first_name="James")
    assert incomplete.ok
    lead_id = incomplete.data["lead_id"]
    assert book(service, sandbox, lead_id).code == "contact_required"
    assert len(service.snapshot(sandbox)["tours"]) == 0
    complete = lead(service, sandbox, "complete")
    assert (
        book(service, sandbox, complete, "weekend", "2026-11-14").code == "closed_day"
    )
    assert book(service, sandbox, complete, "old", "2026-11-08").code == "past_slot"
    assert (
        book(service, sandbox, complete, "meeting", TUESDAY, "14:00").code
        == "slot_unavailable"
    )
    assert (
        book(service, sandbox, complete, "bad-time", MONDAY, "2pm").code
        == "invalid_slot"
    )
    assert (
        book(service, sandbox, complete, "too-soon", MONDAY, "08:00").code
        == "invalid_slot"
    )
    assert (
        invoke(
            service,
            sandbox,
            "book_tour",
            "no-confirm",
            date=MONDAY,
            time="09:00",
            lead_id=complete,
            confirmed=False,
        ).code
        == "invalid_request"
    )
    assert (
        invoke(
            service,
            sandbox,
            "book_tour",
            "string-confirm",
            date=MONDAY,
            time="09:00",
            lead_id=complete,
            confirmed="true",
        ).code
        == "invalid_request"
    )
    assert len(service.snapshot(sandbox)["tours"]) == 0


def test_availability_can_go_stale_but_commit_rechecks(backend):
    service, sandbox = backend
    first_lead = lead(service, sandbox, "a", email="a@example.test")
    second_lead = lead(service, sandbox, "b", email="b@example.test")
    assert any(
        s["time"] == "10:00"
        for s in invoke(service, sandbox, "check_tour_availability", date=MONDAY).data[
            "slots"
        ]
    )
    assert book(service, sandbox, first_lead, "first", MONDAY, "10:00").ok
    loser = book(service, sandbox, second_lead, "second", MONDAY, "10:00")
    assert loser.code == "slot_taken" and not loser.state_verified
    assert len(service.snapshot(sandbox)["tours"]) == 1


def test_concurrent_writers_cannot_double_book(backend):
    service, sandbox = backend
    first_lead = lead(service, sandbox, "race-a", email="race-a@example.test")
    second_lead = lead(service, sandbox, "race-b", email="race-b@example.test")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                book, service, sandbox, person, f"race-{index}", WEDNESDAY, "11:00"
            )
            for index, person in enumerate((first_lead, second_lead))
        ]
        results = [future.result() for future in futures]
    assert sorted(result.code for result in results) == ["booked", "slot_taken"]
    assert len(service.snapshot(sandbox)["tours"]) == 1


def test_faults_lost_slot_and_contradictory_success_have_no_tour(tmp_path):
    lost = CanonicalBackend(
        tmp_path / "lost.db",
        clock=FixedClock(NOW),
        test_faults=TestFaults(lost_slots=frozenset({(WEDNESDAY, "10:00")})),
    )
    sandbox = lost.create_sandbox()
    person = lead(lost, sandbox)
    assert any(
        s["time"] == "10:00"
        for s in invoke(lost, sandbox, "check_tour_availability", date=WEDNESDAY).data[
            "slots"
        ]
    )
    result = book(lost, sandbox, person, "lost", WEDNESDAY, "10:00")
    assert (
        not result.ok
        and result.code == "slot_taken"
        and lost.snapshot(sandbox)["tours"] == []
    )
    malformed = CanonicalBackend(
        tmp_path / "malformed.db",
        clock=FixedClock(NOW),
        test_faults=TestFaults(missing_confirmation_id=True),
    )
    other = malformed.create_sandbox()
    other_person = lead(malformed, other)
    bad = book(malformed, other, other_person)
    assert (
        not bad.ok
        and bad.code == "backend_contract_error"
        and malformed.snapshot(other)["tours"] == []
    )
    assert not validate_booking_response(
        {"success": True, "confirmation_id": None, "error": "slot_taken"}
    ).ok
    assert not validate_booking_response({"success": True, "confirmation_id": True}).ok


def test_timeout_after_commit_reconciles_without_rewrite(tmp_path):
    service = CanonicalBackend(
        tmp_path / "timeout.db",
        clock=FixedClock(NOW),
        test_faults=TestFaults(timeout_after_commit_tools=frozenset({"book_tour"})),
    )
    sandbox = service.create_sandbox()
    person = lead(service, sandbox)
    result = book(service, sandbox, person)
    assert result.ok and result.state_verified
    assert (
        service.reconcile_operation(sandbox, "book_tour", "booking-1").model_dump()
        == result.model_dump()
    )
    assert book(service, sandbox, person).model_dump() == result.model_dump()
    assert len(service.snapshot(sandbox)["tours"]) == 1
    assert (
        service.reconcile_operation(sandbox, "book_tour", "absent").code
        == "unknown_outcome"
    )


def test_reschedule_failure_preserves_old_slot_and_success_keeps_id(backend):
    service, sandbox = backend
    person = lead(service, sandbox)
    booked = book(service, sandbox, person)
    confirmation_id = booked.data["confirmation_id"]
    failed = invoke(
        service,
        sandbox,
        "reschedule_tour",
        "bad-move",
        confirmation_id=confirmation_id,
        date=TUESDAY,
        time="14:00",
        confirmed=True,
    )
    assert not failed.ok and failed.code == "slot_unavailable"
    assert service.snapshot(sandbox)["tours"][0]["local_time"] == "09:00"
    missing = invoke(
        service,
        sandbox,
        "reschedule_tour",
        "missing",
        confirmation_id="T-nope",
        date=WEDNESDAY,
        time="09:00",
        confirmed=True,
    )
    assert missing.code == "not_found"
    other = book(
        service,
        sandbox,
        lead(service, sandbox, "other-person"),
        "other-booking",
        WEDNESDAY,
        "10:00",
    )
    assert other.ok
    occupied = invoke(
        service,
        sandbox,
        "reschedule_tour",
        "occupied",
        confirmation_id=confirmation_id,
        date=WEDNESDAY,
        time="10:00",
        confirmed=True,
    )
    assert occupied.code == "slot_taken"
    assert (
        next(
            row
            for row in service.snapshot(sandbox)["tours"]
            if row["id"] == confirmation_id
        )["local_time"]
        == "09:00"
    )
    moved = invoke(
        service,
        sandbox,
        "reschedule_tour",
        "good-move",
        confirmation_id=confirmation_id,
        date=WEDNESDAY,
        time="09:00",
        confirmed=True,
    )
    assert (
        moved.ok
        and moved.state_verified
        and moved.data["confirmation_id"] == confirmation_id
    )
    tour = next(
        row
        for row in service.snapshot(sandbox)["tours"]
        if row["id"] == confirmation_id
    )
    assert (tour["local_date"], tour["local_time"], tour["status"]) == (
        WEDNESDAY,
        "09:00",
        "booked",
    )
    assert book(service, sandbox, lead(service, sandbox, "new"), "old-slot").ok


def test_cancel_missing_id_already_canceled_and_frees_slot(backend):
    service, sandbox = backend
    person = lead(service, sandbox)
    assert (
        invoke(
            service,
            sandbox,
            "cancel_tour",
            "missing",
            confirmation_id="T-missing",
            confirmed=True,
        ).code
        == "not_found"
    )
    booked = book(service, sandbox, person)
    confirmation_id = booked.data["confirmation_id"]
    canceled = invoke(
        service,
        sandbox,
        "cancel_tour",
        "cancel-1",
        confirmation_id=confirmation_id,
        confirmed=True,
    )
    assert canceled.ok and canceled.code == "canceled" and canceled.state_verified
    again = invoke(
        service,
        sandbox,
        "cancel_tour",
        "cancel-2",
        confirmation_id=confirmation_id,
        confirmed=True,
    )
    assert again.ok and again.code == "already_canceled" and again.state_verified
    assert (
        invoke(
            service,
            sandbox,
            "cancel_tour",
            "cancel-1",
            confirmation_id=confirmation_id,
            confirmed=True,
        ).model_dump()
        == canceled.model_dump()
    )
    assert service.snapshot(sandbox)["tours"][0]["status"] == "canceled"
    assert book(service, sandbox, lead(service, sandbox, "another"), "new-booking").ok
    assert book(service, sandbox, person).code == "state_changed"


def test_lead_correction_preserves_id_and_does_not_merge_shared_phone(backend):
    service, sandbox = backend
    first = lead(service, sandbox, "first", phone="(212) 555-0100")
    second = lead(
        service, sandbox, "second", phone="(212) 555-0100", email="other@example.test"
    )
    assert first != second
    corrected = invoke(
        service,
        sandbox,
        "upsert_lead",
        "correction",
        lead_id=first,
        phone="212-555-0199",
    )
    assert corrected.ok and corrected.data["lead_id"] == first
    records = {row["id"]: row for row in service.snapshot(sandbox)["leads"]}
    assert (
        records[first]["phone"] == "212-555-0199"
        and records[second]["phone"] == "(212) 555-0100"
    )
    assert records[first]["email"] == "james@example.test"
    assert (
        invoke(service, sandbox, "upsert_lead", "bad", email="not-an-email").code
        == "invalid_contact"
    )
    assert len(service.snapshot(sandbox)["leads"]) == 2


def test_request_only_tools_are_durable_and_idempotent(backend):
    service, sandbox = backend
    person = lead(service, sandbox)
    callback = invoke(
        service,
        sandbox,
        "schedule_callback",
        "callback",
        lead_id=person,
        best_time="Wednesday afternoon",
        confirmed=True,
    )
    transfer = invoke(
        service,
        sandbox,
        "transfer_to_human",
        "transfer",
        reason="caller asked for staff",
        authorized=True,
    )
    brochure = invoke(
        service,
        sandbox,
        "send_brochure",
        "brochure",
        lead_id=person,
        address="145 Fake Street, Charlotte, NC 28203",
        address_confirmed=True,
    )
    assert [
        (result.code, result.state_verified)
        for result in (callback, transfer, brochure)
    ] == [
        ("callback_queued", True),
        ("transfer_requested", True),
        ("brochure_queued", True),
    ]
    state = service.snapshot(sandbox)
    assert state["callbacks"][0]["status"] == "queued"
    assert state["transfers"][0]["status"] == "requested"
    assert state["brochures"][0]["status"] == "queued"
    assert (
        invoke(
            service,
            sandbox,
            "schedule_callback",
            "callback",
            lead_id=person,
            best_time="Wednesday afternoon",
            confirmed=True,
        ).model_dump()
        == callback.model_dump()
    )
    assert (
        invoke(
            service,
            sandbox,
            "transfer_to_human",
            "transfer",
            reason="caller asked for staff",
            authorized=True,
        ).model_dump()
        == transfer.model_dump()
    )
    assert (
        invoke(
            service,
            sandbox,
            "send_brochure",
            "brochure",
            lead_id=person,
            address="145 Fake Street, Charlotte, NC 28203",
            address_confirmed=True,
        ).model_dump()
        == brochure.model_dump()
    )
    state = service.snapshot(sandbox)
    assert (
        len(state["callbacks"])
        == len(state["transfers"])
        == len(state["brochures"])
        == 1
    )


def test_requests_reject_missing_lead_contact_address_and_authorization(backend):
    service, sandbox = backend
    no_contact = invoke(
        service, sandbox, "upsert_lead", "partial", first_name="Jane"
    ).data["lead_id"]
    assert (
        invoke(
            service,
            sandbox,
            "schedule_callback",
            "no-contact",
            lead_id=no_contact,
            best_time="tomorrow",
            confirmed=True,
        ).code
        == "contact_required"
    )
    assert (
        invoke(
            service,
            sandbox,
            "schedule_callback",
            "no-lead",
            lead_id="L-none",
            best_time="tomorrow",
            confirmed=True,
        ).code
        == "lead_not_found"
    )
    assert (
        invoke(
            service,
            sandbox,
            "send_brochure",
            "bad-address",
            lead_id=no_contact,
            address="home",
            address_confirmed=True,
        ).code
        == "invalid_address"
    )
    assert (
        invoke(
            service,
            sandbox,
            "send_brochure",
            "missing-zip",
            lead_id=no_contact,
            address="145 Fake Street, Charlotte, NC",
            address_confirmed=True,
        ).code
        == "invalid_address"
    )
    assert (
        invoke(
            service,
            sandbox,
            "transfer_to_human",
            "not-authorized",
            reason="pricing",
            authorized=False,
        ).code
        == "invalid_request"
    )
    assert (
        invoke(
            service,
            sandbox,
            "book_tour",
            None,
            date=MONDAY,
            time="09:00",
            lead_id=no_contact,
            confirmed=True,
        ).code
        == "missing_idempotency_key"
    )
    state = service.snapshot(sandbox)
    assert (
        state["callbacks"]
        == state["transfers"]
        == state["brochures"]
        == state["tours"]
        == []
    )


def test_failed_booking_key_replay_does_not_mutate_after_slot_frees(backend):
    service, sandbox = backend
    first = lead(service, sandbox, "first")
    second = lead(service, sandbox, "second")
    booked = book(service, sandbox, first, "first-booking")
    rejected = book(service, sandbox, second, "rejected")
    assert rejected.code == "slot_taken"
    invoke(
        service,
        sandbox,
        "cancel_tour",
        "first-cancel",
        confirmation_id=booked.data["confirmation_id"],
        confirmed=True,
    )
    assert (
        book(service, sandbox, second, "rejected").model_dump() == rejected.model_dump()
    )
    assert len(service.snapshot(sandbox)["tours"]) == 1


def test_sandbox_isolation_for_reads_and_writes(backend):
    service, first_sandbox = backend
    second_sandbox = service.create_sandbox()
    person = lead(service, first_sandbox)
    booking = book(service, first_sandbox, person)
    assert service.snapshot(second_sandbox)["tours"] == []
    assert book(service, second_sandbox, person, "other").code == "lead_not_found"
    assert (
        invoke(
            service,
            second_sandbox,
            "cancel_tour",
            "cross",
            confirmation_id=booking.data["confirmation_id"],
            confirmed=True,
        ).code
        == "not_found"
    )
    assert service.snapshot(first_sandbox)["tours"][0]["status"] == "booked"
    assert (
        invoke(service, second_sandbox, "check_tour_availability", date=MONDAY).data[
            "slots"
        ][0]["time"]
        == "09:00"
    )
