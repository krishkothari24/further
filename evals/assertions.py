"""Persisted-state and tool-trace oracle; spoken quality is graded separately."""

import hashlib
from typing import Any


FACTS: dict[str, tuple[tuple[str, str], ...]] = {
    "F01": (("pricing", "independent_living_from"),),
    "F02": (("pricing", "entrance_fee"),),
    "F03": (("pricing", "entrance_fee_waiver"),),
    "F04": (("pets", "dog_weight_limit_lbs"),),
    "F05": (("memory_care", "offered"),),
    "F06": (("care_types", "couples_policy"), ("memory_care", "dementia_suitability")),
    "F07": (("dietary", "kosher"), ("dietary", "low_sodium")),
    "F08": (
        ("pricing", "assisted_living_from"),
        ("pricing", "two_bedroom_assisted_living"),
    ),
    "F09": (("room_types", "individual_thermostat"),),
    "F11": (
        ("pricing", "monthly_inclusions"),
        ("room_types", "general_air_conditioning"),
    ),
    "F12": (("pricing", "entrance_fee_waiver"),),
    "F14": (("careers", "current_openings"),),
    "F17": (("amenities", "gym"),),
    "F18": (("parking", "resident_cars"),),
    "F22": (("phone", "main"),),
    "F23": (("amenities", "gym"), ("amenities", "elevators")),
    "S04": (("pricing", "monthly_inclusions"), ("room_types", "individual_thermostat")),
    "S05": (("dietary", "kosher"), ("dietary", "low_sodium")),
    "S06": (("memory_care", "offered"), ("care_types", "couples_policy")),
    "S07": (("pets", "dog_weight_limit_lbs"),),
    "S08": (
        ("pricing", "assisted_living_from"),
        ("pricing", "two_bedroom_assisted_living"),
    ),
    "S09": (("careers", "current_openings"),),
    "S11": (("pricing", "entrance_fee"), ("pricing", "entrance_fee_waiver")),
}
KNOWN_CASES = {f"F{index:02d}" for index in range(1, 25)} | {
    f"S{index:02d}" for index in range(1, 19)
}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _outcomes(metadata: dict) -> list[dict]:
    return [
        outcome for turn in metadata["turns"] for outcome in turn["action_outcomes"]
    ]


def _has_outcome(metadata: dict, kind: str, code: str | None = None) -> bool:
    return any(
        outcome["kind"] == kind
        and outcome["verified"] == (not kind.startswith("not_"))
        and (code is None or outcome["code"] == code)
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


def _event(metadata: dict, tool: str, code: str | None = None) -> bool:
    return any(
        event.get("tool_name") == tool
        and (code is None or event.get("outcome") == code)
        for event in metadata["events"]
    )


def _check(case: str, metadata: dict) -> list[str]:
    state = metadata["final_state"]
    tours, leads = state["tours"], state["leads"]
    failures: list[str] = []

    def require(condition: bool, detail: str) -> None:
        if not condition:
            failures.append(detail)

    require(case in KNOWN_CASES, "unmapped case ID")

    for topic, field in FACTS.get(case, ()):
        require(
            _fact(metadata, topic, field), f"missing canonical read {topic}.{field}"
        )
    if case.startswith("F"):
        require(not tours, "single-turn case created a tour")
    if case in {"F03", "F12", "F13", "F14", "F18", "F21", "F24"}:
        require(
            not _outcomes(metadata)
            or all(not o["verified"] for o in _outcomes(metadata)),
            "unexpected write",
        )
    if case == "F15":
        require(
            len(state["transfers"]) == 1
            and _has_outcome(metadata, "transfer_requested"),
            "human request not recorded",
        )
    if case == "F16":
        require(not state["callbacks"], "callback recorded without details")
    if case in {"F19", "F20"}:
        require(
            _event(metadata, "check_tour_availability"), "availability was not checked"
        )
    if case == "F21":
        require(
            metadata["turns"][0]["status"] == "clarification_required",
            "noisy time was not clarified",
        )
    if case == "F24":
        require(not state["brochures"], "brochure queued without destination")
    if case == "S01":
        require(
            len(tours) == 1
            and tours[0]["status"] == "booked"
            and _has_outcome(metadata, "booked"),
            "tour not verified",
        )
        require(len(leads) == 1, "lead not persisted")
        require(
            _event(metadata, "check_tour_availability", "closed_day"),
            "closed slot was not handled",
        )
    elif case == "S02":
        require(
            len(tours) == 1
            and tours[0]["id"] == metadata["preloaded"].get("tour_id")
            and tours[0]["status"] == "canceled",
            "seeded tour not canceled",
        )
        require(
            _has_outcome(metadata, "rescheduled")
            and _has_outcome(metadata, "canceled"),
            "move/cancel outcomes missing",
        )
    elif case == "S03":
        require(
            not tours and _has_outcome(metadata, "not_booked", "slot_taken"),
            "lost slot was booked",
        )
    elif case == "S10":
        require(
            len(state["transfers"]) == 1
            and _has_outcome(metadata, "transfer_requested"),
            "human request not recorded",
        )
    elif case == "S12":
        require(not metadata["turns"][0]["action_outcomes"], "premature noisy write")
        require(
            len(tours) == 1
            and len(leads) == 1
            and leads[0]["phone_sha256"] == _sha("212-555-0101"),
            "correction was not persisted",
        )
    elif case == "S13":
        require(
            len(state["callbacks"]) == 1
            and state["callbacks"][0]["status"] == "queued"
            and _has_outcome(metadata, "callback_queued"),
            "callback request missing",
        )
    elif case == "S14":
        require(
            len(state["brochures"]) == 1
            and state["brochures"][0]["address_sha256"]
            == _sha("145 Fake Street, Charlotte, NC 28203")
            and _has_outcome(metadata, "brochure_queued"),
            "brochure request missing",
        )
    elif case == "S15":
        require(
            not any(
                o["kind"] in {"canceled", "rescheduled"} for o in _outcomes(metadata)
            ),
            "invalid ID changed tour",
        )
    elif case == "S16":
        require(
            not tours and _event(metadata, "check_tour_availability", "closed_day"),
            "closed day accepted",
        )
    elif case == "S17":
        require(
            not tours
            and _has_outcome(metadata, "not_booked", "backend_contract_error"),
            "malformed success accepted",
        )
    elif case == "S18":
        require(
            len(tours) == 1
            and len(metadata["turns"]) == 3
            and metadata["turns"][1]["turn_id"] == metadata["turns"][2]["turn_id"],
            "retry duplicated tour",
        )
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
