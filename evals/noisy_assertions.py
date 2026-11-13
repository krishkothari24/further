"""Critical state and turn-by-turn oracles for live noisy-transcript cases."""

import hashlib
from typing import Any

from evals.assertions import _fact
from evals.noisy_profiles import PLANS


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _verified(turn: dict, kind: str) -> bool:
    return any(
        outcome["kind"] == kind and outcome["verified"]
        for outcome in turn["action_outcomes"]
    )


def _check(case: str, metadata: dict) -> list[str]:
    failures: list[str] = []
    turns = metadata["turns"]
    state = metadata["final_state"]
    snapshots = [turn["state_after"] for turn in turns]

    def require(condition: bool, detail: str) -> None:
        if not condition:
            failures.append(detail)

    require(metadata["mode"] == "live", "case did not use live runtime")
    require(metadata["noisy_plan_id"] == case, "wrong caller plan")
    require(len(turns) == len(PLANS[case].turns), "missing caller turns")
    require(
        sum(event["stage"] == "interpretation_received" for event in metadata["events"])
        == len(turns),
        "a turn lacked typed model interpretation",
    )
    require(
        all(
            "@" not in str(event) and "212-555" not in str(event)
            for event in metadata["events"]
        ),
        "event contained raw contact",
    )

    tours, leads = state["tours"], state["leads"]
    if case in {"N01", "N02", "N03", "N05", "N06"}:
        expected = {
            "N01": ("2026-11-18", "10:00"),
            "N02": ("2026-11-12", "11:00"),
            "N03": ("2026-11-12", "11:00"),
            "N05": ("2026-11-12", "11:00"),
            "N06": ("2026-11-12", "14:00"),
        }[case]
        require(
            len(tours) == 1
            and tours[0]["status"] == "booked"
            and (tours[0]["local_date"], tours[0]["local_time"]) == expected,
            "wrong final booked tour",
        )
        require(len(leads) == 1, "expected one confirmed lead")
        require(_verified(turns[-1], "booked"), "final turn lacked verified booking")
        require(
            all(not step["tours"] for step in snapshots[:-1]),
            "tour persisted before final approval",
        )
    if case == "N01":
        require(
            leads and leads[0]["email_sha256"] == _sha("jamie.demo@example.test"),
            "spelled email not confirmed correctly",
        )
    elif case == "N02":
        require(
            not snapshots[2]["leads"] and not turns[2]["action_outcomes"],
            "mixed yes/no caused a lead write",
        )
        require(_verified(turns[3], "lead_saved"), "clear correction did not save lead")
    elif case == "N03":
        require(not snapshots[3]["tours"], "old slot booked during changed readback")
    elif case == "N04":
        require(
            not tours and all(not step["tours"] for step in snapshots),
            "negated approval booked a tour",
        )
        require(not _verified(turns[-1], "booked"), "negated approval reported booking")
    elif case == "N05":
        require(not snapshots[2]["leads"], "phone correction skipped readback")
        require(
            leads and leads[0]["phone_digits_sha256"] == _sha("2125550108"),
            "wrong corrected phone persisted",
        )
        require(_verified(turns[3], "lead_saved"), "corrected phone was not confirmed")
    elif case == "N06":
        require(
            turns[0]["status"] == "clarification_required"
            and not snapshots[0]["tours"]
            and not snapshots[0]["leads"],
            "misheard date/time was treated as final",
        )
    elif case == "N07":
        require(
            not snapshots[0]["transfers"] and not turns[0]["action_outcomes"],
            "negated human request recorded a transfer",
        )
        require(
            len(state["transfers"]) == 1
            and state["transfers"][0]["status"] == "requested"
            and _verified(turns[1], "transfer_requested"),
            "explicit human request was not recorded once",
        )
    elif case == "N08":
        tour_id = metadata["preloaded"].get("tour_id")
        require(
            len(snapshots[0]["tours"]) == 1
            and snapshots[0]["tours"][0]["id"] == tour_id
            and snapshots[0]["tours"][0]["status"] == "booked",
            "self-correction canceled the seeded tour",
        )
        require(
            len(tours) == 1
            and tours[0]["id"] == tour_id
            and tours[0]["status"] == "canceled"
            and not _verified(turns[1], "canceled")
            and _verified(turns[2], "canceled"),
            "explicit cancellation did not update the same tour",
        )
    elif case == "N09":
        require(
            _fact(metadata, "pricing", "entrance_fee")
            and _fact(metadata, "pets", "dog_weight_limit_lbs")
            and _fact(metadata, "room_types", "individual_thermostat"),
            "run-on facts were not individually retrieved",
        )
        require(not tours and not leads, "factual question caused a write")
    return failures


def grade(output: str, context: dict[str, Any]) -> dict[str, Any]:
    case = context.get("vars", {}).get("case_id")
    metadata = context.get("metadata") or (context.get("providerResponse") or {}).get(
        "metadata"
    )
    if (
        not isinstance(case, str)
        or case not in PLANS
        or not isinstance(metadata, dict)
        or not output
    ):
        return {
            "pass": False,
            "score": 0,
            "reason": "missing or unknown noisy case/evidence",
        }
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
        else "turn-by-turn persisted-state oracle passed",
        "namedScores": {"critical_state": 0 if failures else 1},
    }
