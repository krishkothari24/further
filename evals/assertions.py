"""Deterministic promptfoo oracles over real runtime metadata and persisted state."""

import hashlib
import re
from typing import Any


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _outcomes(metadata: dict) -> list[dict]:
    return [
        outcome for turn in metadata["turns"] for outcome in turn["action_outcomes"]
    ]


def _has_outcome(metadata: dict, kind: str, *, code: str | None = None) -> bool:
    return any(
        outcome["kind"] == kind and (code is None or outcome["code"] == code)
        for outcome in _outcomes(metadata)
    )


def _fact(metadata: dict, topic: str, field: str) -> bool:
    return any(
        event.get("tool_name") == "get_community_info"
        and event.get("outcome") == "facts_returned"
        and event.get("redacted_params", {}).get("topic") == topic
        and event.get("redacted_params", {}).get("field") == field
        for event in metadata["events"]
    )


def _phrase(metadata: dict, phrase: str) -> bool:
    return (
        phrase.lower()
        in " ".join(turn["spoken_text"] for turn in metadata["turns"]).lower()
    )


def _event(metadata: dict, name: str, code: str | None = None) -> bool:
    return any(
        event.get("tool_name") == name
        and (code is None or event.get("outcome") == code)
        for event in metadata["events"]
    )


def _no_false_success(metadata: dict) -> bool:
    for turn in metadata["turns"]:
        spoken = turn["spoken_text"].lower()
        outcomes = turn["action_outcomes"]
        if "your tour is booked" in spoken and not any(
            o["kind"] == "booked"
            and o["verified"]
            and o["entity_id"] in turn["spoken_text"]
            for o in outcomes
        ):
            return False
        if re.search(r"tour\s+t-[a-z0-9]+\s+is canceled", spoken) and not any(
            o["kind"] == "canceled" and o["verified"] for o in outcomes
        ):
            return False
        if "i've queued your callback" in spoken and not any(
            o["kind"] == "callback_queued" and o["verified"] for o in outcomes
        ):
            return False
        if "i've queued your brochure" in spoken and not any(
            o["kind"] == "brochure_queued" and o["verified"] for o in outcomes
        ):
            return False
        if "i've recorded your request" in spoken and not any(
            o["kind"] == "transfer_requested" and o["verified"] for o in outcomes
        ):
            return False
    return True


def _check(case: str, metadata: dict) -> list[str]:
    state = metadata["final_state"]
    tours, leads = state["tours"], state["leads"]
    failures: list[str] = []

    def require(condition: bool, detail: str) -> None:
        if not condition:
            failures.append(detail)

    require(_no_false_success(metadata), "speech claims an unverified action")
    if case.startswith("F"):
        require(not tours, "single-turn case created a tour")
    if case == "F01":
        require(
            _fact(metadata, "pricing", "independent_living_from")
            and _phrase(metadata, "2,000 dollars per month"),
            "independent starting price",
        )
    elif case == "F02":
        require(
            _fact(metadata, "pricing", "entrance_fee")
            and _phrase(metadata, "3,500 dollars")
            and not _phrase(metadata, "2,500"),
            "canonical entrance fee",
        )
    elif case in {"F03", "F12"}:
        require(
            _fact(metadata, "pricing", "entrance_fee_waiver")
            and _phrase(metadata, "can't confirm an entrance fee waiver")
            and not tours,
            "unsupported waiver",
        )
    elif case == "F04":
        require(
            _fact(metadata, "pets", "dog_weight_limit_lbs")
            and _phrase(metadata, "30 pounds")
            and _phrase(metadata, "dog's weight"),
            "dog limit without guarantee",
        )
    elif case == "F05":
        require(
            _fact(metadata, "memory_care", "offered")
            and _phrase(metadata, "does not offer dedicated memory care"),
            "memory care absence",
        )
    elif case == "F06":
        require(
            _fact(metadata, "care_types", "couples_policy")
            and _fact(metadata, "memory_care", "dementia_suitability")
            and _phrase(metadata, "can't assess"),
            "couple/clinical uncertainty",
        )
    elif case == "F07":
        require(
            _fact(metadata, "dietary", "kosher")
            and _fact(metadata, "dietary", "low_sodium")
            and _phrase(metadata, "can't confirm Kosher")
            and _phrase(metadata, "Low sodium"),
            "dietary distinction",
        )
    elif case == "F08":
        require(
            _fact(metadata, "pricing", "assisted_living_from")
            and _fact(metadata, "pricing", "two_bedroom_assisted_living")
            and _phrase(metadata, "3,000 dollars per month"),
            "room price distinction",
        )
    elif case == "F09":
        require(
            _fact(metadata, "room_types", "individual_thermostat")
            and _phrase(metadata, "can't confirm individual"),
            "thermostat unknown",
        )
    elif case == "F10":
        require(_phrase(metadata, "AI assistant"), "AI identity")
    elif case == "F11":
        require(
            _fact(metadata, "pricing", "monthly_inclusions")
            and _fact(metadata, "room_types", "general_air_conditioning"),
            "both compound facts",
        )
    elif case == "F13":
        require(
            _phrase(metadata, "don't have a confirmed purchasing contact"),
            "vendor routing",
        )
    elif case == "F14":
        require(
            _fact(metadata, "careers", "current_openings")
            and "http" not in metadata["turns"][0]["spoken_text"],
            "no invented job opening or URL",
        )
    elif case == "F15":
        require(
            len(state["transfers"]) == 1
            and state["transfers"][0]["status"] == "requested"
            and _has_outcome(metadata, "transfer_requested"),
            "recorded handoff",
        )
    elif case == "F16":
        require(
            not state["callbacks"] and _phrase(metadata, "confirm"),
            "callback needs confirmed contact",
        )
    elif case == "F17":
        require(
            _fact(metadata, "amenities", "gym") and _phrase(metadata, "gym"),
            "grounded gym",
        )
    elif case == "F18":
        require(
            _fact(metadata, "parking", "resident_cars")
            and _phrase(metadata, "can't confirm the resident car policy"),
            "resident car policy unknown",
        )
    elif case in {"F19", "F20"}:
        require(
            _event(metadata, "check_tour_availability")
            and _phrase(metadata, "isn't available"),
            "unavailable tour slot",
        )
    elif case == "F21":
        require(
            metadata["turns"][0]["status"] == "clarification_required"
            and not _event(metadata, "book_tour"),
            "noisy date clarification",
        )
    elif case == "F22":
        require(
            _fact(metadata, "phone", "main") and _phrase(metadata, "850-445-8362"),
            "canonical phone",
        )
    elif case == "F23":
        require(
            _fact(metadata, "amenities", "gym")
            and _fact(metadata, "amenities", "elevators")
            and len(metadata["turns"][0]["spoken_text"]) < 350,
            "concise amenity summary",
        )
    elif case == "F24":
        require(
            not state["brochures"] and _phrase(metadata, "confirm"),
            "brochure needs destination/contact",
        )
    elif case == "S01":
        require(
            len(tours) == 1
            and tours[0]["status"] == "booked"
            and (tours[0]["local_date"], tours[0]["local_time"])
            == ("2026-11-17", "15:00"),
            "correct booked tour",
        )
        require(
            len(leads) == 1
            and (leads[0]["first_name"], leads[0]["last_name"]) == ("James", "Carter"),
            "caller identity",
        )
        require(
            _has_outcome(metadata, "booked")
            and _event(metadata, "check_tour_availability", "closed_day")
            and _event(metadata, "check_tour_availability", "availability_returned"),
            "booking/closed slot trace",
        )
    elif case == "S02":
        require(
            len(tours) == 1
            and tours[0]["id"] == metadata["preloaded"].get("tour_id")
            and tours[0]["status"] == "canceled",
            "same tour canceled",
        )
        require(
            _has_outcome(metadata, "rescheduled")
            and _has_outcome(metadata, "canceled"),
            "move/cancel outcomes",
        )
    elif case == "S03":
        require(
            not tours
            and _has_outcome(metadata, "not_booked", code="slot_taken")
            and _event(metadata, "book_tour", "slot_taken"),
            "lost slot rejected",
        )
    elif case == "S04":
        require(
            _fact(metadata, "pricing", "monthly_inclusions")
            and _fact(metadata, "room_types", "individual_thermostat"),
            "both compound unknowns",
        )
    elif case == "S05":
        require(
            _fact(metadata, "dietary", "kosher")
            and _fact(metadata, "dietary", "low_sodium")
            and _phrase(metadata, "can't confirm Kosher"),
            "dietary separation",
        )
    elif case == "S06":
        require(
            _fact(metadata, "memory_care", "offered")
            and _fact(metadata, "care_types", "couples_policy")
            and _phrase(metadata, "can't assess"),
            "no suitability guarantee",
        )
    elif case == "S07":
        require(
            _fact(metadata, "pets", "dog_weight_limit_lbs")
            and _phrase(metadata, "30 pounds")
            and _phrase(metadata, "dog's weight"),
            "dog limit",
        )
    elif case == "S08":
        require(
            _fact(metadata, "pricing", "assisted_living_from")
            and _fact(metadata, "pricing", "two_bedroom_assisted_living")
            and _phrase(metadata, "3,000 dollars"),
            "exact room price unknown",
        )
    elif case == "S09":
        require(
            not tours
            and _phrase(metadata, "don't have a confirmed purchasing contact")
            and _fact(metadata, "careers", "current_openings")
            and "http" not in " ".join(t["spoken_text"] for t in metadata["turns"]),
            "vendor/job claims",
        )
    elif case == "S10":
        require(
            len(state["transfers"]) == 1
            and state["transfers"][0]["status"] == "requested"
            and _has_outcome(metadata, "transfer_requested")
            and not _phrase(metadata, "connected you"),
            "simulated handoff",
        )
    elif case == "S11":
        require(
            _fact(metadata, "pricing", "entrance_fee")
            and _fact(metadata, "pricing", "entrance_fee_waiver")
            and _phrase(metadata, "3,500 dollars"),
            "waiver cannot override fee",
        )
    elif case == "S12":
        require(
            metadata["turns"][0]["status"] == "clarification_required"
            and not metadata["turns"][0]["action_outcomes"],
            "no premature noisy write",
        )
        require(
            len(tours) == 1
            and tours[0]["status"] == "booked"
            and len(leads) == 1
            and leads[0]["phone_sha256"] == _sha("212-555-0101"),
            "corrected lead and tour",
        )
    elif case == "S13":
        require(
            len(state["callbacks"]) == 1
            and state["callbacks"][0]["status"] == "queued"
            and _has_outcome(metadata, "callback_queued")
            and not _phrase(metadata, "will call"),
            "queued callback only",
        )
    elif case == "S14":
        require(
            len(state["brochures"]) == 1
            and state["brochures"][0]["status"] == "queued"
            and state["brochures"][0]["address_sha256"]
            == _sha("145 Fake Street, Charlotte, NC 28203")
            and _has_outcome(metadata, "brochure_queued"),
            "queued brochure only",
        )
    elif case == "S15":
        require(
            not tours
            and not any(
                o["kind"] in {"canceled", "rescheduled"} for o in _outcomes(metadata)
            ),
            "invalid tour ID cannot change state",
        )
    elif case == "S16":
        require(
            not tours
            and _event(metadata, "check_tour_availability", "availability_returned")
            and _event(metadata, "check_tour_availability", "closed_day"),
            "Monday/Saturday boundary",
        )
    elif case == "S17":
        require(
            not tours
            and _has_outcome(metadata, "not_booked", code="backend_contract_error")
            and not _phrase(metadata, "your tour is booked"),
            "malformed success rejected",
        )
    elif case == "S18":
        require(
            len(tours) == 1
            and tours[0]["status"] == "booked"
            and len(metadata["turns"]) == 3
            and metadata["turns"][1]["turn_id"] == metadata["turns"][2]["turn_id"]
            and metadata["turns"][1]["spoken_text"]
            == metadata["turns"][2]["spoken_text"],
            "duplicate submission idempotent",
        )
    else:
        failures.append("unmapped case ID")
    return failures


def grade(output: str, context: dict[str, Any]) -> dict[str, Any]:
    case = context.get("vars", {}).get("case_id")
    metadata = context.get("metadata") or (context.get("providerResponse") or {}).get(
        "metadata"
    )
    if not isinstance(case, str) or not isinstance(metadata, dict):
        return {
            "pass": False,
            "score": 0,
            "reason": "missing case ID or runtime metadata",
        }
    required = {
        "final_state",
        "turns",
        "events",
        "prompt_version",
        "fixture_version",
        "mode",
    }
    if not required.issubset(metadata) or not output:
        return {"pass": False, "score": 0, "reason": "incomplete provider evidence"}
    try:
        failures = _check(case, metadata)
    except (KeyError, TypeError, IndexError) as exc:
        return {
            "pass": False,
            "score": 0,
            "reason": f"invalid evidence shape: {type(exc).__name__}",
        }
    return {
        "pass": not failures,
        "score": 0 if failures else 1,
        "reason": "; ".join(failures)
        if failures
        else "persisted-state and trace oracle passed",
        "namedScores": {"critical_state": 0 if failures else 1},
    }
