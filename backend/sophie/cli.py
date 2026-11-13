"""Interactive text conversation with an explicit sandbox, conversation, and clock."""

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from .backend import CanonicalBackend
from .runtime import SophieRuntime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sophie text playground")
    parser.add_argument("--db", type=Path, required=True, help="Local SQLite path")
    parser.add_argument("--sandbox", required=True, help="Existing sandbox ID or 'new'")
    parser.add_argument(
        "--conversation", required=True, help="Existing conversation ID or 'new'"
    )
    parser.add_argument(
        "--clock",
        help="Optional fixed ISO clock for a reproducible scenario; omit for live time",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Diagnostic only: no language interpretation or business action without a model",
    )
    args = parser.parse_args(argv)
    if args.sandbox != "new" and args.clock:
        parser.error("--clock only applies to --sandbox new")
    simulated_now = None
    if args.clock:
        try:
            simulated_now = datetime.fromisoformat(args.clock)
        except ValueError:
            parser.error("--clock must be an ISO timestamp with UTC offset")
        if simulated_now.tzinfo is None or simulated_now.utcoffset() is None:
            parser.error("--clock must include a UTC offset")
    try:
        backend = CanonicalBackend(args.db)
        sandbox = (
            backend.create_sandbox(simulated_now=simulated_now)
            if args.sandbox == "new"
            else args.sandbox
        )
        backend.sandbox_now(sandbox)
        runtime = SophieRuntime(backend, offline=args.offline)
        conversation = (
            runtime.create_conversation(sandbox)
            if args.conversation == "new"
            else args.conversation
        )
        runtime.get_state(sandbox, conversation)  # also enforces sandbox ownership
    except (KeyError, ValueError) as exc:
        parser.exit(2, f"Cannot start Sophie: {exc}\n")
    print(
        f"Sandbox: {sandbox}\nConversation: {conversation}\nClock: {backend.sandbox_now(sandbox).isoformat()}"
    )
    print("Commands: /state, /events, /quit")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line == "/quit":
            break
        if line == "/state":
            # Tour inspection only; never print lead/contact records or raw transcripts.
            tours = backend.snapshot(sandbox)["tours"]
            print(
                json.dumps(
                    [
                        {
                            key: row[key]
                            for key in (
                                "id",
                                "local_date",
                                "local_time",
                                "timezone",
                                "status",
                            )
                        }
                        for row in tours
                    ],
                    indent=2,
                )
            )
            continue
        if line == "/events":
            print(
                json.dumps(
                    [
                        event.model_dump(exclude_none=True)
                        for event in runtime.get_events(sandbox, conversation)
                    ],
                    indent=2,
                )
            )
            continue
        if line.startswith("/"):
            print("Unknown command.")
            continue
        if not line:
            continue
        turn = runtime.handle_turn(sandbox, conversation, uuid.uuid4().hex, line)
        print("Sophie> " + turn.spoken_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
