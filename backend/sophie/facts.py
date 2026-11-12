"""Versioned, field-provenance ACME fixture; never infer facts from caller text."""

import json
from importlib.resources import files
from typing import Any


FACT_REVISION = "fixture-v1"


def load_facts() -> dict[str, dict[str, dict[str, Any]]]:
    path = files("sophie").joinpath("fixtures/community_facts.json")
    return json.loads(path.read_text(encoding="utf-8"))
