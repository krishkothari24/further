"""Transactional sandbox services. Caller text cannot reach test faults or write metadata."""

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Protocol
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from .contracts import TOOL_INPUTS, StrictModel, ToolResult
from .facts import FACT_REVISION, load_facts


COMMUNITY_TZ = ZoneInfo("America/New_York")
WRITES = frozenset(
    {
        "book_tour",
        "reschedule_tour",
        "cancel_tour",
        "upsert_lead",
        "schedule_callback",
        "transfer_to_human",
        "send_brochure",
    }
)


class Clock(Protocol):
    def now_utc(self) -> datetime: ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now_utc(self) -> datetime:
        if self.instant.tzinfo is None or self.instant.utcoffset() is None:
            raise ValueError("fixed clock must be timezone-aware")
        return self.instant.astimezone(timezone.utc)


@dataclass(frozen=True)
class TestFaults:
    """Constructor-only test harness controls; never a tool input or caller option."""

    __test__ = False

    lost_slots: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    missing_confirmation_id: bool = False
    timeout_after_commit_tools: frozenset[str] = field(default_factory=frozenset)


def _result(ok: bool, code: str, data: dict[str, Any] | None = None) -> ToolResult:
    return ToolResult(ok=ok, code=code, data=data)


def validate_booking_response(payload: Mapping[str, Any]) -> ToolResult:
    """Reject the inherited contradictory success shape before any success claim."""

    confirmation_id = payload.get("confirmation_id")
    if (
        payload.get("error") is not None
        or payload.get("success") is not True
        or not isinstance(confirmation_id, str)
        or not confirmation_id.strip()
    ):
        return _result(False, "backend_contract_error")
    return _result(True, "booked", {"confirmation_id": confirmation_id})


class CanonicalBackend:
    def __init__(
        self,
        db_path: str | Path,
        *,
        clock: Clock | None = None,
        test_faults: TestFaults | None = None,
    ):
        self.db_path = str(db_path)
        self.clock = clock or SystemClock()
        self._test_faults = test_faults or TestFaults()
        self.facts = load_facts()
        self._init_db()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sandboxes (
                    id TEXT PRIMARY KEY, fixture_revision TEXT NOT NULL,
                    simulated_now_utc TEXT NOT NULL, created_at_utc TEXT NOT NULL,
                    clock_is_fixed INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS sandbox_fixtures (
                    sandbox_id TEXT PRIMARY KEY REFERENCES sandboxes(id),
                    scenario_id TEXT, faults_json TEXT NOT NULL,
                    seed_json TEXT NOT NULL, retired_at_utc TEXT
                );
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL REFERENCES sandboxes(id),
                    first_name TEXT, last_name TEXT, phone TEXT, email TEXT, notes TEXT,
                    created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL,
                    UNIQUE (sandbox_id, id)
                );
                CREATE TABLE IF NOT EXISTS tours (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL REFERENCES sandboxes(id),
                    lead_id TEXT NOT NULL, local_date TEXT NOT NULL, local_time TEXT NOT NULL,
                    timezone TEXT NOT NULL, starts_at_utc TEXT NOT NULL,
                    party_size INTEGER NOT NULL CHECK (party_size >= 1),
                    status TEXT NOT NULL CHECK (status IN ('booked', 'canceled')),
                    created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL,
                    FOREIGN KEY (sandbox_id, lead_id) REFERENCES leads(sandbox_id, id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_tour_per_slot
                    ON tours(sandbox_id, local_date, local_time) WHERE status = 'booked';
                CREATE TABLE IF NOT EXISTS callbacks (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL REFERENCES sandboxes(id),
                    lead_id TEXT NOT NULL, best_time TEXT NOT NULL, status TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    FOREIGN KEY (sandbox_id, lead_id) REFERENCES leads(sandbox_id, id)
                );
                CREATE TABLE IF NOT EXISTS transfers (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL REFERENCES sandboxes(id),
                    reason TEXT NOT NULL, status TEXT NOT NULL, created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS brochures (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL REFERENCES sandboxes(id),
                    lead_id TEXT NOT NULL, postal_address TEXT NOT NULL, status TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    FOREIGN KEY (sandbox_id, lead_id) REFERENCES leads(sandbox_id, id)
                );
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL REFERENCES sandboxes(id),
                    tool_name TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL, result_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    UNIQUE (sandbox_id, tool_name, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL REFERENCES sandboxes(id),
                    state_json TEXT NOT NULL, revision INTEGER NOT NULL,
                    created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL,
                    UNIQUE (sandbox_id, id)
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL, client_turn_id TEXT NOT NULL,
                    caller_text TEXT NOT NULL, status TEXT NOT NULL,
                    result_json TEXT, created_at_utc TEXT NOT NULL,
                    UNIQUE (sandbox_id, conversation_id, client_turn_id),
                    FOREIGN KEY (sandbox_id, conversation_id) REFERENCES conversations(sandbox_id, id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, sandbox_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL, turn_id TEXT NOT NULL,
                    seq INTEGER NOT NULL, stage TEXT NOT NULL,
                    payload_json TEXT NOT NULL, timestamp_utc TEXT NOT NULL,
                    FOREIGN KEY (sandbox_id, conversation_id) REFERENCES conversations(sandbox_id, id)
                );
            """)
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(sandboxes)")
            }
            if "clock_is_fixed" not in columns:
                conn.execute(
                    "ALTER TABLE sandboxes ADD COLUMN clock_is_fixed INTEGER NOT NULL DEFAULT 1"
                )

    def create_sandbox(self, *, simulated_now: datetime | None = None) -> str:
        instant = simulated_now or self.clock.now_utc()
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("sandbox clock must be timezone-aware")
        sandbox_id = "S-" + uuid.uuid4().hex
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO sandboxes (id, fixture_revision, simulated_now_utc, created_at_utc, clock_is_fixed) VALUES (?, ?, ?, ?, ?)",
                (
                    sandbox_id,
                    FACT_REVISION,
                    instant.astimezone(timezone.utc).isoformat(),
                    self._audit_now(),
                    int(
                        simulated_now is not None or isinstance(self.clock, FixedClock)
                    ),
                ),
            )
            conn.execute(
                "INSERT INTO sandbox_fixtures VALUES (?, NULL, '{}', '{}', NULL)",
                (sandbox_id,),
            )
        return sandbox_id

    def fixture_info(self, sandbox_id: str) -> dict[str, Any]:
        """Read sandbox-scoped fixture metadata; retired sandboxes are inaccessible to API users."""
        with self._connection() as conn:
            sandbox = self._sandbox(conn, sandbox_id)
            if sandbox is None:
                raise KeyError(sandbox_id)
            row = conn.execute(
                "SELECT * FROM sandbox_fixtures WHERE sandbox_id=?", (sandbox_id,)
            ).fetchone()
            if row is not None and row["retired_at_utc"] is not None:
                raise KeyError(sandbox_id)
            return {
                "scenario_id": row["scenario_id"] if row else None,
                "faults": json.loads(row["faults_json"]) if row else {},
                "seed": json.loads(row["seed_json"]) if row else {},
                "fixture_version": sandbox["fixture_revision"],
            }

    def configure_fixture(
        self,
        sandbox_id: str,
        *,
        scenario_id: str,
        faults: dict[str, Any],
        seed: dict[str, Any],
    ) -> None:
        """Trusted fixture-loader method. No tool or HTTP endpoint accepts arbitrary flags."""
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT retired_at_utc FROM sandbox_fixtures WHERE sandbox_id=?",
                (sandbox_id,),
            ).fetchone()
            if row is None or row["retired_at_utc"] is not None:
                raise KeyError(sandbox_id)
            conn.execute(
                "UPDATE sandbox_fixtures SET scenario_id=?, faults_json=?, seed_json=? WHERE sandbox_id=?",
                (
                    scenario_id,
                    json.dumps(faults, sort_keys=True),
                    json.dumps(seed, sort_keys=True),
                    sandbox_id,
                ),
            )
            conn.commit()

    def retire_sandbox(self, sandbox_id: str) -> None:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "UPDATE sandbox_fixtures SET retired_at_utc=? WHERE sandbox_id=? AND retired_at_utc IS NULL",
                (self._audit_now(), sandbox_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(sandbox_id)
            conn.commit()

    def _faults_for(self, conn: sqlite3.Connection, sandbox_id: str) -> TestFaults:
        row = conn.execute(
            "SELECT faults_json FROM sandbox_fixtures WHERE sandbox_id=?", (sandbox_id,)
        ).fetchone()
        fixture = json.loads(row["faults_json"]) if row else {}
        return TestFaults(
            lost_slots=self._test_faults.lost_slots
            | frozenset(tuple(slot) for slot in fixture.get("lost_slots", [])),
            missing_confirmation_id=self._test_faults.missing_confirmation_id
            or fixture.get("missing_confirmation_id", False),
            timeout_after_commit_tools=self._test_faults.timeout_after_commit_tools
            | frozenset(fixture.get("timeout_after_commit_tools", [])),
        )

    def sandbox_now(self, sandbox_id: str) -> datetime:
        """Read a scenario's fixed instant or the current community-local time."""

        with self._connection() as conn:
            sandbox = self._sandbox(conn, sandbox_id)
            if sandbox is None:
                raise KeyError(sandbox_id)
            return self._now_for_sandbox(sandbox)

    def sandbox_clock_is_fixed(self, sandbox_id: str) -> bool:
        with self._connection() as conn:
            sandbox = self._sandbox(conn, sandbox_id)
            if sandbox is None:
                raise KeyError(sandbox_id)
            return bool(sandbox["clock_is_fixed"])

    def _now_for_sandbox(self, sandbox: sqlite3.Row) -> datetime:
        instant = (
            datetime.fromisoformat(sandbox["simulated_now_utc"])
            if sandbox["clock_is_fixed"]
            else self.clock.now_utc()
        )
        return instant.astimezone(COMMUNITY_TZ)

    def call(
        self,
        tool_name: str,
        sandbox_id: str,
        params: Mapping[str, Any],
        *,
        operation_key: str | None = None,
    ) -> ToolResult:
        model_type = TOOL_INPUTS.get(tool_name)
        if model_type is None:
            return _result(False, "unknown_tool")
        try:
            model = model_type.model_validate(params)
        except ValidationError:
            return _result(False, "invalid_request")
        if tool_name in WRITES:
            if not operation_key or not operation_key.strip():
                return _result(False, "missing_idempotency_key")
            return self._write(tool_name, sandbox_id, model, operation_key)
        with self._connection() as conn:
            sandbox = self._sandbox(conn, sandbox_id)
            if sandbox is None:
                return _result(False, "sandbox_not_found")
            if tool_name == "get_community_info":
                topic = self.facts.get(model.topic)
                if topic is None:
                    return _result(False, "fact_not_found")
                if model.field is not None:
                    fact = topic.get(model.field)
                    if fact is None:
                        return _result(False, "fact_not_found")
                    topic = {model.field: fact}
                return ToolResult(
                    ok=True,
                    code="facts_returned",
                    data={
                        "topic": model.topic,
                        "fields": topic,
                        "revision": FACT_REVISION,
                    },
                    state_verified=True,
                )
            return self._availability(conn, sandbox_id, sandbox, model.date)

    def _write(
        self, tool: str, sandbox_id: str, model: StrictModel, key: str
    ) -> ToolResult:
        request_hash = hashlib.sha256(
            model.model_dump_json(exclude_none=False).encode()
        ).hexdigest()
        try:
            with self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                sandbox = self._sandbox(conn, sandbox_id)
                if sandbox is None:
                    conn.rollback()
                    return _result(False, "sandbox_not_found")
                faults = self._faults_for(conn, sandbox_id)
                prior = conn.execute(
                    "SELECT * FROM operations WHERE sandbox_id=? AND tool_name=? AND idempotency_key=?",
                    (sandbox_id, tool, key),
                ).fetchone()
                if prior:
                    conn.rollback()
                    if prior["request_hash"] != request_hash:
                        return _result(False, "idempotency_conflict")
                    return self.reconcile_operation(sandbox_id, tool, key)
                action = getattr(self, "_do_" + tool)
                result = action(conn, sandbox_id, sandbox, model)
                operation_id = "O-" + uuid.uuid4().hex
                result.operation_id = operation_id
                if result.ok:
                    if not self._verify_result(conn, tool, sandbox_id, result):
                        conn.rollback()
                        return _result(False, "backend_contract_error")
                    result.state_verified = True
                conn.execute(
                    "INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        operation_id,
                        sandbox_id,
                        tool,
                        key,
                        request_hash,
                        result.model_dump_json(),
                        self._audit_now(),
                    ),
                )
                conn.commit()
            if tool in faults.timeout_after_commit_tools:
                return self.reconcile_operation(sandbox_id, tool, key)
            return result
        except sqlite3.IntegrityError:
            return _result(
                False,
                "slot_taken"
                if tool in {"book_tour", "reschedule_tour"}
                else "invalid_request",
            )
        except sqlite3.Error:
            return _result(False, "infrastructure_error")

    def reconcile_operation(self, sandbox_id: str, tool: str, key: str) -> ToolResult:
        """Read-only lookup after an uncertain write; never retries the mutation."""

        with self._connection() as conn:
            row = conn.execute(
                "SELECT result_json FROM operations WHERE sandbox_id=? AND tool_name=? AND idempotency_key=?",
                (sandbox_id, tool, key),
            ).fetchone()
            if row is None:
                return _result(False, "unknown_outcome")
            result = ToolResult.model_validate_json(row["result_json"])
            if result.ok and not self._verify_result(conn, tool, sandbox_id, result):
                return ToolResult(
                    ok=False, code="state_changed", operation_id=result.operation_id
                )
            return result

    def snapshot(self, sandbox_id: str) -> dict[str, list[dict[str, Any]]]:
        """Read-only persisted-state inspection for tests and later inspector API."""

        with self._connection() as conn:
            if self._sandbox(conn, sandbox_id) is None:
                raise KeyError(sandbox_id)
            return {
                name: [
                    dict(row)
                    for row in conn.execute(
                        f"SELECT * FROM {name} WHERE sandbox_id=? ORDER BY id",
                        (sandbox_id,),
                    )
                ]
                for name in (
                    "leads",
                    "tours",
                    "callbacks",
                    "transfers",
                    "brochures",
                    "operations",
                )
            }

    @staticmethod
    def _sandbox(conn: sqlite3.Connection, sandbox_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT s.* FROM sandboxes AS s LEFT JOIN sandbox_fixtures AS f ON f.sandbox_id=s.id "
            "WHERE s.id=? AND (f.retired_at_utc IS NULL)",
            (sandbox_id,),
        ).fetchone()

    @staticmethod
    def _audit_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_date(value: str) -> date | None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_time(value: str) -> time | None:
        if not re.fullmatch(r"\d{2}:\d{2}", value):
            return None
        try:
            parsed = time.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.minute == 0 and 9 <= parsed.hour <= 18 else None

    def _slot(
        self, sandbox: sqlite3.Row, date_text: str, time_text: str
    ) -> tuple[datetime | None, str | None]:
        day, hour = self._parse_date(date_text), self._parse_time(time_text)
        if day is None or hour is None:
            return None, "invalid_slot"
        local = datetime.combine(day, hour, tzinfo=COMMUNITY_TZ)
        if local.astimezone(timezone.utc).astimezone(COMMUNITY_TZ) != local:
            return None, "invalid_slot"
        now = self._now_for_sandbox(sandbox)
        if local <= now:
            return None, "past_slot"
        if day.weekday() >= 5:
            return None, "closed_day"
        if day.weekday() == 1 and hour.hour == 14:
            return None, "slot_unavailable"
        return local, None

    def _availability(
        self,
        conn: sqlite3.Connection,
        sandbox_id: str,
        sandbox: sqlite3.Row,
        date_text: str,
    ) -> ToolResult:
        day = self._parse_date(date_text)
        if day is None:
            return _result(False, "invalid_date")
        now = self._now_for_sandbox(sandbox)
        if day < now.date():
            return _result(False, "past_date")
        if day.weekday() >= 5:
            return _result(False, "closed_day", {"date": date_text, "slots": []})
        taken = {
            row["local_time"]
            for row in conn.execute(
                "SELECT local_time FROM tours WHERE sandbox_id=? AND local_date=? AND status='booked'",
                (sandbox_id, date_text),
            )
        }
        slots = []
        for hour in range(9, 19):
            time_text = f"{hour:02}:00"
            local, error = self._slot(sandbox, date_text, time_text)
            if error is None and time_text not in taken:
                slots.append(
                    {
                        "date": date_text,
                        "time": time_text,
                        "timezone": COMMUNITY_TZ.key,
                        "starts_at_utc": local.astimezone(timezone.utc).isoformat(),
                    }
                )
        return ToolResult(
            ok=True,
            code="availability_returned",
            data={"date": date_text, "slots": slots},
            state_verified=True,
        )

    @staticmethod
    def _lead(
        conn: sqlite3.Connection, sandbox_id: str, lead_id: str
    ) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM leads WHERE sandbox_id=? AND id=?", (sandbox_id, lead_id)
        ).fetchone()

    @staticmethod
    def _tour(
        conn: sqlite3.Connection, sandbox_id: str, confirmation_id: str
    ) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM tours WHERE sandbox_id=? AND id=?",
            (sandbox_id, confirmation_id),
        ).fetchone()

    @staticmethod
    def _valid_contact(lead: Mapping[str, Any]) -> bool:
        phone = lead["phone"] or ""
        email = lead["email"] or ""
        phone_ok = (
            bool(re.fullmatch(r"[+()\d .-]+", phone))
            and 10 <= len(re.sub(r"\D", "", phone)) <= 15
        )
        email_ok = (
            bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)) if email else False
        )
        return phone_ok or email_ok

    def _do_upsert_lead(
        self,
        conn: sqlite3.Connection,
        sandbox_id: str,
        sandbox: sqlite3.Row,
        model: StrictModel,
    ) -> ToolResult:
        values = model.model_dump(exclude_none=True)
        lead_id = values.pop("lead_id", None)
        if not values:
            return _result(False, "invalid_request")
        if "phone" in values and (
            not re.fullmatch(r"[+()\d .-]+", values["phone"])
            or not 10 <= len(re.sub(r"\D", "", values["phone"])) <= 15
        ):
            return _result(False, "invalid_contact")
        if "email" in values and not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]
        ):
            return _result(False, "invalid_contact")
        if lead_id:
            if self._lead(conn, sandbox_id, lead_id) is None:
                return _result(False, "not_found")
            updates = ", ".join(f"{field}=?" for field in values)
            conn.execute(
                f"UPDATE leads SET {updates}, updated_at_utc=? WHERE sandbox_id=? AND id=?",
                (*values.values(), self._audit_now(), sandbox_id, lead_id),
            )
        else:
            lead_id = "L-" + uuid.uuid4().hex
            conn.execute(
                "INSERT INTO leads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    lead_id,
                    sandbox_id,
                    values.get("first_name"),
                    values.get("last_name"),
                    values.get("phone"),
                    values.get("email"),
                    values.get("notes"),
                    self._audit_now(),
                    self._audit_now(),
                ),
            )
        return _result(True, "lead_saved", {"lead_id": lead_id, **values})

    def _do_book_tour(
        self,
        conn: sqlite3.Connection,
        sandbox_id: str,
        sandbox: sqlite3.Row,
        model: StrictModel,
    ) -> ToolResult:
        lead = self._lead(conn, sandbox_id, model.lead_id)
        if lead is None:
            return _result(False, "lead_not_found")
        if (
            not lead["first_name"]
            or not lead["last_name"]
            or not self._valid_contact(lead)
        ):
            return _result(False, "contact_required")
        local, error = self._slot(sandbox, model.date, model.time)
        if error:
            return _result(False, error)
        faults = self._faults_for(conn, sandbox_id)
        if (model.date, model.time) in faults.lost_slots:
            return _result(False, "slot_taken")
        if conn.execute(
            "SELECT 1 FROM tours WHERE sandbox_id=? AND local_date=? AND local_time=? AND status='booked'",
            (sandbox_id, model.date, model.time),
        ).fetchone():
            return _result(False, "slot_taken")
        if faults.missing_confirmation_id:
            return validate_booking_response(
                {"success": True, "confirmation_id": None, "error": "slot_taken"}
            )
        confirmation_id = "T-" + uuid.uuid4().hex
        checked = validate_booking_response(
            {"success": True, "confirmation_id": confirmation_id}
        )
        if not checked.ok:
            return checked
        conn.execute(
            "INSERT INTO tours VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'booked', ?, ?)",
            (
                confirmation_id,
                sandbox_id,
                model.lead_id,
                model.date,
                model.time,
                COMMUNITY_TZ.key,
                local.astimezone(timezone.utc).isoformat(),
                model.party_size,
                self._audit_now(),
                self._audit_now(),
            ),
        )
        return _result(
            True,
            "booked",
            {
                "confirmation_id": confirmation_id,
                "lead_id": model.lead_id,
                "date": model.date,
                "time": model.time,
                "timezone": COMMUNITY_TZ.key,
                "starts_at_utc": local.astimezone(timezone.utc).isoformat(),
                "party_size": model.party_size,
                "status": "booked",
            },
        )

    def _do_reschedule_tour(
        self,
        conn: sqlite3.Connection,
        sandbox_id: str,
        sandbox: sqlite3.Row,
        model: StrictModel,
    ) -> ToolResult:
        tour = self._tour(conn, sandbox_id, model.confirmation_id)
        if tour is None:
            return _result(False, "not_found")
        if tour["status"] != "booked":
            return _result(False, "already_canceled")
        local, error = self._slot(sandbox, model.date, model.time)
        if error:
            return _result(False, error)
        if tour["local_date"] == model.date and tour["local_time"] == model.time:
            return _result(
                True,
                "unchanged",
                {
                    "confirmation_id": tour["id"],
                    "date": model.date,
                    "time": model.time,
                    "status": "booked",
                },
            )
        if (model.date, model.time) in self._faults_for(conn, sandbox_id).lost_slots:
            return _result(False, "slot_taken")
        if conn.execute(
            "SELECT 1 FROM tours WHERE sandbox_id=? AND local_date=? AND local_time=? AND status='booked'",
            (sandbox_id, model.date, model.time),
        ).fetchone():
            return _result(False, "slot_taken")
        conn.execute(
            "UPDATE tours SET local_date=?, local_time=?, starts_at_utc=?, updated_at_utc=? WHERE sandbox_id=? AND id=?",
            (
                model.date,
                model.time,
                local.astimezone(timezone.utc).isoformat(),
                self._audit_now(),
                sandbox_id,
                tour["id"],
            ),
        )
        return _result(
            True,
            "rescheduled",
            {
                "confirmation_id": tour["id"],
                "date": model.date,
                "time": model.time,
                "status": "booked",
            },
        )

    def _do_cancel_tour(
        self,
        conn: sqlite3.Connection,
        sandbox_id: str,
        sandbox: sqlite3.Row,
        model: StrictModel,
    ) -> ToolResult:
        tour = self._tour(conn, sandbox_id, model.confirmation_id)
        if tour is None:
            return _result(False, "not_found")
        if tour["status"] == "canceled":
            return _result(
                True,
                "already_canceled",
                {"confirmation_id": tour["id"], "status": "canceled"},
            )
        conn.execute(
            "UPDATE tours SET status='canceled', updated_at_utc=? WHERE sandbox_id=? AND id=?",
            (self._audit_now(), sandbox_id, tour["id"]),
        )
        return _result(
            True, "canceled", {"confirmation_id": tour["id"], "status": "canceled"}
        )

    def _do_schedule_callback(
        self,
        conn: sqlite3.Connection,
        sandbox_id: str,
        sandbox: sqlite3.Row,
        model: StrictModel,
    ) -> ToolResult:
        lead = self._lead(conn, sandbox_id, model.lead_id)
        if lead is None:
            return _result(False, "lead_not_found")
        if not self._valid_contact(lead) or not model.best_time.strip():
            return _result(False, "contact_required")
        request_id = "C-" + uuid.uuid4().hex
        conn.execute(
            "INSERT INTO callbacks VALUES (?, ?, ?, ?, 'queued', ?)",
            (
                request_id,
                sandbox_id,
                model.lead_id,
                model.best_time.strip(),
                self._audit_now(),
            ),
        )
        return _result(
            True,
            "callback_queued",
            {
                "request_id": request_id,
                "lead_id": model.lead_id,
                "best_time": model.best_time.strip(),
                "status": "queued",
            },
        )

    def _do_transfer_to_human(
        self,
        conn: sqlite3.Connection,
        sandbox_id: str,
        sandbox: sqlite3.Row,
        model: StrictModel,
    ) -> ToolResult:
        if not model.reason.strip():
            return _result(False, "invalid_request")
        request_id = "X-" + uuid.uuid4().hex
        conn.execute(
            "INSERT INTO transfers VALUES (?, ?, ?, 'requested', ?)",
            (request_id, sandbox_id, model.reason.strip(), self._audit_now()),
        )
        return _result(
            True,
            "transfer_requested",
            {
                "request_id": request_id,
                "reason": model.reason.strip(),
                "status": "requested",
            },
        )

    def _do_send_brochure(
        self,
        conn: sqlite3.Connection,
        sandbox_id: str,
        sandbox: sqlite3.Row,
        model: StrictModel,
    ) -> ToolResult:
        if self._lead(conn, sandbox_id, model.lead_id) is None:
            return _result(False, "lead_not_found")
        address = model.address.strip()
        if not re.fullmatch(
            r"\d+\s+[^,]+,\s*[^,]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?", address
        ):
            return _result(False, "invalid_address")
        request_id = "B-" + uuid.uuid4().hex
        conn.execute(
            "INSERT INTO brochures VALUES (?, ?, ?, ?, 'queued', ?)",
            (request_id, sandbox_id, model.lead_id, address, self._audit_now()),
        )
        return _result(
            True,
            "brochure_queued",
            {
                "request_id": request_id,
                "lead_id": model.lead_id,
                "address": address,
                "status": "queued",
            },
        )

    def _verify_result(
        self, conn: sqlite3.Connection, tool: str, sandbox_id: str, result: ToolResult
    ) -> bool:
        data = result.data or {}
        if tool == "upsert_lead":
            row = self._lead(conn, sandbox_id, data.get("lead_id", ""))
            return bool(
                row and all(row[k] == v for k, v in data.items() if k != "lead_id")
            )
        if tool in {"book_tour", "reschedule_tour", "cancel_tour"}:
            row = self._tour(conn, sandbox_id, data.get("confirmation_id", ""))
            if not row or row["status"] != data.get("status"):
                return False
            if tool != "cancel_tour":
                return (
                    row["local_date"] == data.get("date")
                    and row["local_time"] == data.get("time")
                    and (
                        tool != "book_tour"
                        or row["lead_id"] == data.get("lead_id")
                        and row["starts_at_utc"] == data.get("starts_at_utc")
                        and row["party_size"] == data.get("party_size")
                        and row["timezone"] == data.get("timezone")
                        and bool(
                            (lead := self._lead(conn, sandbox_id, row["lead_id"]))
                            and lead["first_name"]
                            and lead["last_name"]
                            and self._valid_contact(lead)
                        )
                    )
                )
            return True
        table = {
            "schedule_callback": "callbacks",
            "transfer_to_human": "transfers",
            "send_brochure": "brochures",
        }[tool]
        row = conn.execute(
            f"SELECT * FROM {table} WHERE sandbox_id=? AND id=?",
            (sandbox_id, data.get("request_id", "")),
        ).fetchone()
        if not row or row["status"] != data.get("status"):
            return False
        if tool == "schedule_callback":
            return row["lead_id"] == data.get("lead_id") and row[
                "best_time"
            ] == data.get("best_time")
        if tool == "send_brochure":
            return row["lead_id"] == data.get("lead_id") and row[
                "postal_address"
            ] == data.get("address")
        return row["reason"] == data.get("reason")
