"""Declarative S01-S18 sandbox presets. No conversational outputs are scripted."""

import json
from datetime import datetime
from importlib.resources import files
from typing import Any

from pydantic import Field

from .backend import CanonicalBackend
from .contracts import StrictModel


class SeedLead(StrictModel):
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None


class SeedTour(StrictModel):
    date: str
    time: str


class FaultSpec(StrictModel):
    lost_slots: list[list[str]] = Field(default_factory=list)
    missing_confirmation_id: bool = False
    timeout_after_commit_tools: list[str] = Field(default_factory=list)


class ScenarioSpec(StrictModel):
    id: str
    name: str
    goal: str
    clock: str | None = None
    preloaded_lead: SeedLead | None = None
    preloaded_tour: SeedTour | None = None
    faults: FaultSpec = Field(default_factory=FaultSpec)
    user_profile: dict[str, str] = Field(default_factory=dict)
    suggested_turns: list[str] = Field(default_factory=list)


class ScenarioCatalog:
    def __init__(self):
        data = json.loads(
            files("sophie").joinpath("fixtures/scenarios.json").read_text()
        )
        self.version = data["fixture_version"]
        self.base_clock = datetime.fromisoformat(data["base_clock"])
        self.base_user_profile: dict[str, str] = data["base_user_profile"]
        specs = [ScenarioSpec.model_validate(item) for item in data["scenarios"]]
        self.specs = {spec.id: spec for spec in specs}
        if len(specs) != 18 or set(self.specs) != {f"S{i:02d}" for i in range(1, 19)}:
            raise ValueError("scenario catalog must contain S01-S18 exactly once")

    def get(self, scenario_id: str) -> ScenarioSpec:
        try:
            return self.specs[scenario_id]
        except KeyError:
            raise KeyError(scenario_id) from None

    def list_metadata(self) -> list[dict[str, Any]]:
        return [
            {
                "id": spec.id,
                "name": spec.name,
                "goal": spec.goal,
                "clock": (
                    datetime.fromisoformat(spec.clock)
                    if spec.clock
                    else self.base_clock
                ).isoformat(),
                "suggested_turns": spec.suggested_turns,
                "user_profile": {**self.base_user_profile, **spec.user_profile},
                "preloaded": bool(spec.preloaded_lead or spec.preloaded_tour),
                "fault_labels": [
                    label
                    for label in (
                        "lost_slot" if spec.faults.lost_slots else None,
                        "malformed_success"
                        if spec.faults.missing_confirmation_id
                        else None,
                    )
                    if label
                ],
            }
            for spec in self.specs.values()
        ]

    def create_sandbox(
        self,
        backend: CanonicalBackend,
        scenario_id: str | None = None,
        *,
        clock_override: datetime | None = None,
    ) -> str:
        spec = self.get(scenario_id) if scenario_id else None
        clock = (
            datetime.fromisoformat(spec.clock)
            if spec and spec.clock
            else (self.base_clock if spec else clock_override)
        )
        sandbox_id = backend.create_sandbox(simulated_now=clock)
        if spec is None:
            return sandbox_id
        # Configure only allowlisted, package-owned flags. Caller transcript and API body cannot provide them.
        faults = spec.faults.model_dump(exclude_defaults=True)
        backend.configure_fixture(
            sandbox_id, scenario_id=scenario_id, faults=faults, seed={}
        )
        seed: dict[str, str] = {}
        if spec.preloaded_lead:
            lead = backend.call(
                "upsert_lead",
                sandbox_id,
                spec.preloaded_lead.model_dump(exclude_none=True),
                operation_key=f"fixture:{scenario_id}:lead",
            )
            if not lead.ok or not lead.state_verified or not lead.data:
                raise RuntimeError("fixture lead could not be created")
            seed["lead_id"] = lead.data["lead_id"]
        if spec.preloaded_tour:
            if not seed.get("lead_id"):
                raise RuntimeError("fixture tour requires a lead")
            tour = backend.call(
                "book_tour",
                sandbox_id,
                {
                    "date": spec.preloaded_tour.date,
                    "time": spec.preloaded_tour.time,
                    "lead_id": seed["lead_id"],
                    "confirmed": True,
                },
                operation_key=f"fixture:{scenario_id}:tour",
            )
            if not tour.ok or not tour.state_verified or not tour.data:
                raise RuntimeError("fixture tour could not be created")
            seed["tour_id"] = tour.data["confirmation_id"]
        backend.configure_fixture(
            sandbox_id, scenario_id=scenario_id, faults=faults, seed=seed
        )
        return sandbox_id

    def reset_sandbox(self, backend: CanonicalBackend, sandbox_id: str) -> str:
        fixture = backend.fixture_info(sandbox_id)
        original_clock = backend.sandbox_now(sandbox_id)
        new_id = self.create_sandbox(
            backend, fixture["scenario_id"], clock_override=original_clock
        )
        backend.retire_sandbox(sandbox_id)
        return new_id
