# M1 — Correct canonical backend and all nine tool services

**Goal:** Durable, transactionally valid services before introducing LLM variability.

## Work

- Create structured fact registry from original mock data with field-level provenance; select and document only safe prompt-only migrations.
- Typed service schemas/map for all nine inherited tools; repair original schema mismatch and broken descriptions without editing `inherited/`.
- Build SQLite schema/repositories for tours, leads, callback requests, transfers, brochures, sandboxes and idempotency keys.
- Availability: timezone-aware future, Monday–Friday, Tuesday 14:00 blocked, normalized local slot enumeration; enforce transaction-level uniqueness on booking.
- Booking: race-safe commit, correct failure payload, persisted confirmation ID; no direct bypass of business rules.
- Reschedule: require correct ID, validate new slot and atomically move; failed change preserves existing booking.
- Cancel: require existing booking; define already-canceled idempotence; absent ID cannot falsely succeed.
- Lead/contact correction, callback/brochure/transfer request-only durable records, no unneeded empty lead on greeting.
- Test-only fault injection interface (missing ID, lost slot, timeout) must be explicit and unreachable from a caller transcript.

## Acceptance evidence

- `pytest` with no LLM key covers each of nine services, contradictory `success=true` payload, Monday/Saturday, Wednesday race, Tuesday meeting, invalid date, stale write, duplicate client request, missing ID cancel, failed reschedule and sandbox isolation.
- Query/read-back confirms each successful write and no side effect after failed write.
- One documented canonical catalog for $3,500 entrance, 30-lb dogs, memory care false.
- Report all tests run and known limitations. **Stop before M2.**
