"""Reconstructed inherited agent. Deliberately retains original prompt/mock behavior."""

import importlib.util
import json
import os
import uuid
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_PROMPT = (ROOT / "inherited/original_prompt.md").read_text()
ORIGINAL_TOOLS = json.loads((ROOT / "inherited/tools.json").read_text())


def _fresh_mock():
    """Load inherited in-memory state anew for every provider call."""
    name = "inherited_mock_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "inherited/mock_tools.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load inherited mock")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_baseline(
    prompt: str, client: Any, *, model: str, max_calls: int = 4
) -> dict[str, Any]:
    mock = _fresh_mock()
    tools = [
        {
            "type": "function",
            "name": item["name"],
            "description": item["description"],
            "parameters": item["parameters"],
            "strict": False,
        }
        for item in ORIGINAL_TOOLS
    ]
    input_items: list[dict] = [{"role": "user", "content": prompt}]
    events = []
    final_text = ""
    input_tokens = 0
    output_tokens = 0
    model_requests = 0
    for index in range(max_calls + 1):
        response = client.responses.create(
            model=model,
            instructions=ORIGINAL_PROMPT,
            input=input_items,
            tools=[] if index == max_calls else tools,
            parallel_tool_calls=False,
            store=False,
        )
        model_requests += 1
        usage = getattr(response, "usage", None)
        input_tokens += getattr(usage, "input_tokens", 0) or 0
        output_tokens += getattr(usage, "output_tokens", 0) or 0
        items = [
            item.model_dump(mode="json", exclude_none=True) for item in response.output
        ]
        input_items.extend(items)
        calls = [item for item in items if item.get("type") == "function_call"]
        if not calls:
            final_text = response.output_text or ""
            break
        if index == max_calls or len(calls) != 1:
            raise RuntimeError("baseline tool-call limit or parallel call")
        item = calls[0]
        name = item["name"]
        if name not in {tool["name"] for tool in ORIGINAL_TOOLS}:
            result = {"error": "unknown_tool"}
        else:
            try:
                args = json.loads(item["arguments"])
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
                # The inherited tool schema says tour_id; the inherited Python function says confirmation_id.
                if name == "reschedule_tour" and "tour_id" in args:
                    args["confirmation_id"] = args.pop("tour_id")
                result = getattr(mock, name)(**args)
            except Exception as exc:
                result = {"error": type(exc).__name__}
        events.append({"tool_name": name, "result": result})
        input_items.append(
            {
                "type": "function_call_output",
                "call_id": item["call_id"],
                "output": json.dumps(result, default=str),
            }
        )
    return {
        "output": final_text,
        "tokenUsage": {
            "prompt": input_tokens,
            "completion": output_tokens,
            "total": input_tokens + output_tokens,
            "numRequests": model_requests,
        },
        "metadata": {
            "baseline": "reconstructed",
            "model_id": model,
            "tool_events": events,
            "mock_state": {
                "tour_count": len(mock.TOURS),
                "lead_count": len(mock.LEADS),
                "callback_count": len(mock.CALLBACKS),
                "transfer_count": len(mock.TRANSFERS),
                "brochure_count": len(mock.BROCHURES),
            },
        },
    }


def call_api(
    prompt: str, options: dict | None = None, context: dict | None = None
) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        return {"error": "OPENAI_API_KEY is required for reconstructed baseline"}
    try:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=0)
        return run_baseline(
            prompt, client, model=os.environ.get("OPENAI_MODEL", "gpt-6.1-sol")
        )
    except Exception as exc:
        return {"error": f"reconstructed baseline failed: {type(exc).__name__}"}
