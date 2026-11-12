"""Opt-in live model smoke check; never run in the offline test suite."""

import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from sophie.backend import CanonicalBackend, FixedClock
from sophie.runtime import SophieRuntime


def main() -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required for this opt-in smoke check.")
        return 2
    with TemporaryDirectory() as directory:
        backend = CanonicalBackend(
            Path(directory) / "smoke.db",
            clock=FixedClock(datetime(2026, 11, 11, 15, tzinfo=timezone.utc)),
        )
        sandbox = backend.create_sandbox()
        runtime = SophieRuntime(backend)
        conversation = runtime.create_conversation(sandbox)
        result = runtime.handle_turn(
            sandbox, conversation, "smoke-1", "What is the entrance fee?"
        )
        passed = result.status == "completed" and "3,500 dollars" in result.spoken_text
        print("Live model smoke:", "PASS" if passed else "FAIL")
        print("Structured event stages:", [event.stage for event in result.events])
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
