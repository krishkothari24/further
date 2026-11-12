# M1 canonical backend contract

The nine original names are kept. `CanonicalBackend.call(name, sandbox_id, params, operation_key=...)` is an internal service boundary, not a caller-text or model tool endpoint. Typed inputs reject unknown fields. Every write requires an operation key and records a result in SQLite. `ok=true` for a write means its row was read back in the same transaction and matched the intended state. A replay with the same key and same request returns the saved result if the state still matches; changed payload is `idempotency_conflict`, and later changed state is `state_changed`.

| Tool | Repaired input | Verified result |
|---|---|---|
| `get_community_info` | `topic`, optional `field` | Catalog fields with value, unit, source, status, revision; unknown topic/field is `fact_not_found` |
| `check_tour_availability` | ISO `date` | Future local hourly slots and UTC instants; Monday–Friday, 09:00–18:00 inclusive, Tuesday 14:00 blocked |
| `book_tour` | `date`, `time` (`HH:MM`), existing `lead_id`, `confirmed=true`, optional `party_size` | Persisted active tour, non-null confirmation ID, local and UTC time, valid full name and email or phone |
| `reschedule_tour` | `confirmation_id`, new `date`/`time`, `confirmed=true` | Same tour ID moved atomically; failure leaves old row unchanged |
| `cancel_tour` | Existing `confirmation_id`, `confirmed=true` | Persisted canceled row; repeat with a new key returns `already_canceled`, missing ID returns `not_found` |
| `upsert_lead` | Meaningful contact/name/notes fields, optional existing `lead_id` | Stable lead ID and persisted corrections; never merges by phone or creates an empty greeting lead |
| `schedule_callback` | Existing contactable `lead_id`, nonblank `best_time`, `confirmed=true` | Durable `queued` request, with no guarantee a human calls |
| `transfer_to_human` | Nonblank `reason`, `authorized=true` | Durable `requested` event, with no live connection claim |
| `send_brochure` | Existing `lead_id`, confirmed US-formatted `address` | Durable `queued` request, with no mailing claim |

## Facts and source decisions

[`backend/sophie/fixtures/community_facts.json`](../backend/sophie/fixtures/community_facts.json) is the single M1 fact registry. Every original `COMMUNITY_INFO` value from the inherited mock is present with `source=mock-original`; a test compares all of them by parsing the original Python without executing it. In particular: entrance fee $3,500, dogs up to 30 lb, and dedicated memory care `false`. The original prompt's gym, elevators, and low-sodium option are included as fictional demo facts with `source=legacy-prompt`. Exact two-bedroom price, individual thermostat, Kosher meals, fee waiver, Medicaid eligibility, dementia suitability, and current hiring are explicitly unknown or require staff confirmation. No couples policy is used to infer clinical suitability.

## Persistence and test faults

Each sandbox has a fixed UTC instant and isolated rows. Tour slots are stored as community-local date/time plus `America/New_York` and an explicit UTC instant. SQLite `BEGIN IMMEDIATE` and a partial unique index on active `(sandbox_id, local_date, local_time)` protect booking and rescheduling. The 18:00 start is retained from the inherited mock; tour duration is unspecified. A canceled tour frees its slot. The service does not expose a public API or authentication at M1.

`TestFaults` is injected only into the Python constructor by a trusted test harness. It can mark a slot lost after availability, supply the inherited contradictory missing-ID booking response, or simulate a timeout after commit. Faults are absent from `call` parameters and caller text. The timeout path reconciles through the saved operation key without repeating the write. The first two faults leave no tour row.

## Known limits

- Contact validation checks practical email/phone syntax, not actual reachability. A future runtime must confirm noisy transcriptions before writes.
- Brochure address validation is US-formatted and syntactic, not postal verification.
- `snapshot` includes local sandbox contact data for tests. The later API must enforce access controls and redaction before exposing it.
- SQLite gives reliable local sandbox transactions; real CRM/calendar writes need their own idempotency and reconciliation design.
