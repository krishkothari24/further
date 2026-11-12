"""Offline M0 checks for the unchanged assignment assets."""

import ast
import hashlib
import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INHERITED = ROOT / "inherited"


def test_original_asset_hashes_match_manifest():
    manifest = (INHERITED / "SHA256.md").read_text(encoding="utf-8")
    entries = re.findall(r"`inherited/([^`]+)`: `([0-9a-f]{64})`", manifest)
    assert len(entries) == 5
    for filename, expected_hash in entries:
        actual_hash = hashlib.sha256((INHERITED / filename).read_bytes()).hexdigest()
        assert actual_hash == expected_hash, filename


def test_tool_json_and_python_parse_with_nine_matching_names():
    tools = json.loads((INHERITED / "tools.json").read_text(encoding="utf-8"))
    python_tree = ast.parse((INHERITED / "mock_tools.py").read_text(encoding="utf-8"))
    functions = {
        node.name for node in python_tree.body if isinstance(node, ast.FunctionDef)
    }
    names = [tool["name"] for tool in tools]
    assert len(names) == len(set(names)) == 9
    assert set(names) <= functions


def test_seed_yaml_parses_and_records_original_variable_mismatch():
    seed = yaml.safe_load(
        (INHERITED / "promptfooconfig.yaml").read_text(encoding="utf-8")
    )
    cases = seed["tests"]
    assert len(cases) == 15
    assert seed["prompts"] == ["{{user_input}}"]
    mismatches = [
        case["description"] for case in cases if "user_input" not in case["vars"]
    ]
    assert mismatches == ["Kosher and low sodium"]
    assert (
        "question"
        in next(case for case in cases if case["description"] == mismatches[0])["vars"]
    )
