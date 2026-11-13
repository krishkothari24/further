"""Fixed caller utterances for live ASR-style regression cases.

These are caller turns only. Sophie always replies through the shared runtime.
"""

from dataclasses import dataclass

from sophie.runtime import SophieRuntime
from sophie.state import TurnResult


@dataclass(frozen=True)
class NoisyPlan:
    fixture_id: str
    turns: tuple[str, ...]


PLANS: dict[str, NoisyPlan] = {
    "N01": NoisyPlan(
        "S01",
        (
            "uh could i pop by for a look next Wednesday at ten in the morning",
            "this is Jamie Demo j a m i e dot d e m o at example dot test",
            "yep that's right",
            "yeah go ahead with that",
        ),
    ),
    "N02": NoisyPlan(
        "S01",
        (
            "can i come see the place next Thursday at eleven",
            "Jamie Demo jamie.demo@example.test",
            "uhhh yes no actually yeash that sounds good",
            "yes Jamie Demo at jamie.demo@example.test is correct",
            "Thursday, November 12, 2026 at 11 a.m.",
            "yes, please book that tour",
        ),
    ),
    "N03": NoisyPlan(
        "S01",
        (
            "let's visit next Wednesday at ten",
            "I'm Jamie Demo and my email is jamie.demo@example.test",
            "that's right",
            "yeah actually make it Thursday at eleven instead",
            "Thursday, November 12, 2026 at 11 a.m.",
            "yes, please book that time",
        ),
    ),
    "N04": NoisyPlan(
        "S01",
        (
            "book a tour next Wednesday at ten",
            "I'm Jamie Demo email jamie.demo@example.test",
            "yes that's right",
            "uh don't book it actually",
        ),
    ),
    "N05": NoisyPlan(
        "S01",
        (
            "book a tour next Thursday at eleven",
            "my name is Jamie Demo and call me at two one two five five five zero one zero zero",
            "wait no it's 212-555-0108 not 212-555-0100",
            "yes 0108 is right",
            "Thursday, November 12, 2026 at 11 a.m.",
            "yes, book that tour",
        ),
    ),
    "N06": NoisyPlan(
        "S01",
        (
            "could we do uh thirs day at too",
            "I mean next Thursday two p.m.",
            "I'm Jamie Demo email jamie.demo@example.test",
            "yeah that's right",
            "yep go ahead",
        ),
    ),
    "N07": NoisyPlan(
        "S01",
        (
            "don't connect me with a person just tell me the price",
            "actually I'm frustrated please get me a real person",
        ),
    ),
    "N08": NoisyPlan(
        "S02",
        (
            "uh cancel my tour no actually don't cancel anything yet",
            "cancel my tour {tour_id}",
            "yes, cancel that tour",
        ),
    ),
    "N09": NoisyPlan(
        "S01",
        (
            "what's the move in money also are big dogs okay and does each room do its own temperature",
        ),
    ),
}


def run_noisy_scenario(
    runtime: SophieRuntime, sandbox_id: str, conversation_id: str, plan_id: str
) -> list[tuple[str, TurnResult, dict]]:
    """Run one isolated plan and capture persisted state after each caller turn."""
    plan = PLANS[plan_id]
    seed = runtime.backend.fixture_info(sandbox_id)["seed"]
    history = []
    for index, template in enumerate(plan.turns, start=1):
        caller = template.replace("{tour_id}", seed.get("tour_id", ""))
        result = runtime.handle_turn(
            sandbox_id, conversation_id, f"noisy-{index}", caller
        )
        if result.status == "error":
            raise RuntimeError(f"runtime error at {plan_id} turn {index}")
        history.append((caller, result, runtime.backend.snapshot(sandbox_id)))
    return history
