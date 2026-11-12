"""M4 HTTP integration checks against the real Sophie runtime and SQLite state."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from sophie.api import create_app
from sophie.scenarios import ScenarioCatalog


@pytest.fixture
def api(tmp_path):
    app = create_app(tmp_path / "api.db", offline=True, allow_test_client=True)
    return TestClient(app), app


def sandbox(client, scenario_id="S01"):
    response = client.post("/api/sandboxes", json={"scenario_id": scenario_id})
    assert response.status_code == 201, response.text
    return response.json()


def conversation(client, sandbox_id):
    response = client.post("/api/conversations", json={"sandbox_id": sandbox_id})
    assert response.status_code == 201, response.text
    return response.json()["conversation_id"]


def turn(client, sandbox_id, conversation_id, number, text):
    response = client.post(
        f"/api/conversations/{conversation_id}/turns",
        json={
            "sandbox_id": sandbox_id,
            "client_turn_id": str(number),
            "caller_text": text,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def prepare_booking(client, sandbox_id, conversation_id, prefix):
    first = turn(
        client,
        sandbox_id,
        conversation_id,
        f"{prefix}-1",
        "Book a tour next Wednesday at 11am.",
    )
    assert first["status"] == "clarification_required"
    turn(
        client,
        sandbox_id,
        conversation_id,
        f"{prefix}-2",
        f"My name is Jamie {prefix}, email jamie.{prefix.lower()}@example.test.",
    )
    confirmed = turn(client, sandbox_id, conversation_id, f"{prefix}-3", "Yes.")
    assert confirmed["action_outcomes"][0]["kind"] == "lead_saved"


def test_catalog_all_18_and_request_validation(api):
    client, app = api
    scenarios = client.get("/api/scenarios")
    assert scenarios.status_code == 200
    assert {item["id"] for item in scenarios.json()} == {
        f"S{i:02d}" for i in range(1, 19)
    }
    assert all(item["suggested_turns"] and item["clock"] for item in scenarios.json())
    assert all(item["user_profile"]["synthetic"] == "true" for item in scenarios.json())
    assert client.get("/api/evaluations").json() == {"status": "not_run", "items": []}
    assert client.post("/api/sandboxes", json={"scenario_id": "S99"}).status_code == 422
    assert (
        client.post(
            "/api/sandboxes", json={"scenario_id": "S03", "lost_slots": []}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/conversations", json={"sandbox_id": "missing"}).status_code
        == 404
    )
    assert ScenarioCatalog().version == "scenarios-m4-v1"
    assert app.state.backend.facts["pricing"]["entrance_fee"]["value"] == 3500


def test_http_turn_trace_state_facts_and_idempotency(api):
    client, app = api
    s = sandbox(client)
    sid = s["sandbox_id"]
    cid = conversation(client, sid)
    price = turn(client, sid, cid, 1, "What is the entrance fee?")
    assert "3,500 dollars" in price["spoken_text"]
    assert price["conversation_id"] == cid
    assert any(event["stage"] == "tool_result" for event in price["events"])
    facts = client.get(f"/api/sandboxes/{sid}/facts").json()
    assert facts["facts"]["pricing"]["entrance_fee"]["value"] == 3500
    assert facts["facts"]["pricing"]["entrance_fee"]["source"] == "mock-original"
    prepare_booking(client, sid, cid, "Demo")
    booked = turn(client, sid, cid, 4, "Yes.")
    replay = turn(client, sid, cid, 4, "Yes.")
    assert replay == booked and booked["action_outcomes"][0]["verified"]
    conflict = turn(client, sid, cid, 4, "Book another tour")
    assert conflict["status"] == "error" and conflict["action_outcomes"] == []
    tour_id = booked["action_outcomes"][0]["entity_id"]
    state = client.get(f"/api/sandboxes/{sid}/state").json()
    assert state["tours"][0]["id"] == tour_id
    events = client.get(
        f"/api/conversations/{cid}/events", params={"sandbox_id": sid}
    ).json()
    assert any(
        event["tool_name"] == "book_tour"
        and event["outcome"] == "booked"
        and event["entity_id"] == tour_id
        for event in events
    )
    assert (
        state["tours"][0]["local_time"] == "11:00"
        and state["tours"][0]["status"] == "booked"
    )
    assert len(app.state.backend.snapshot(sid)["tours"]) == 1
    assert "jamie.demo@example.test" not in str(state)
    assert state["leads"][0]["name_masked"] == "J*** D***"
    events = client.get(
        f"/api/conversations/{cid}/events", params={"sandbox_id": sid}
    ).json()
    assert any(event["outcome"] == "booked" for event in events)
    assert "jamie.demo@example.test" not in str(events)
    transcript = client.get(
        f"/api/conversations/{cid}", params={"sandbox_id": sid}
    ).json()
    assert transcript["revision"] == 5 and len(transcript["messages"]) == 10


def test_s01_price_to_booking_uses_followup_date_and_real_slot(api):
    client, app = api
    sid = sandbox(client, "S01")["sandbox_id"]
    cid = conversation(client, sid)
    price = turn(client, sid, cid, 1, "Hi, how much does your community cost?")
    assert "2,000 dollars per month" in price["spoken_text"]
    medicaid = turn(client, sid, cid, 2, "Do you take Medicaid?")
    assert "don't have confirmed information" in medicaid["spoken_text"]
    sunday = turn(client, sid, cid, 3, "Could I tour next Sunday at 3pm?")
    assert "isn't available" in sunday["spoken_text"]
    tuesday = turn(client, sid, cid, 4, "How about next Tuesday at 2pm?")
    assert "isn't available" in tuesday["spoken_text"]
    alternate = turn(client, sid, cid, 5, "What about 3pm that afternoon?")
    assert "full name" in alternate["spoken_text"]
    turn(
        client, sid, cid, 6, "My name is James Carter, email james.carter@example.test."
    )
    turn(client, sid, cid, 7, "Yes.")
    booked = turn(client, sid, cid, 8, "Yes.")
    assert booked["action_outcomes"][0]["kind"] == "booked"
    row = app.state.backend.snapshot(sid)["tours"][0]
    assert (row["local_date"], row["local_time"], row["status"]) == (
        "2026-11-17",
        "15:00",
        "booked",
    )


def test_s04_s06_s09_s13_s14_s10_cover_partial_facts_and_requests(api):
    client, app = api
    s04 = sandbox(client, "S04")["sandbox_id"]
    c04 = conversation(client, s04)
    combined = turn(
        client,
        s04,
        c04,
        1,
        "What does the monthly price include, and can my mom control the air conditioning in her room?",
    )
    assert combined["spoken_text"].count("team member") >= 2
    s06 = sandbox(client, "S06")["sandbox_id"]
    clinical = turn(
        client,
        s06,
        conversation(client, s06),
        1,
        "Can my mom and dad live together? My mom has dementia.",
    )
    assert "does not offer dedicated memory care" in clinical["spoken_text"]
    assert "can't confirm arrangements for couples" in clinical["spoken_text"]
    s09 = sandbox(client, "S09")["sandbox_id"]
    vendor = turn(
        client,
        s09,
        conversation(client, s09),
        1,
        "I supply food to senior homes. Who handles purchasing?",
    )
    assert "don't have a confirmed purchasing contact" in vendor["spoken_text"]
    s13 = sandbox(client, "S13")["sandbox_id"]
    c13 = conversation(client, s13)
    assert (
        "May I queue"
        in turn(
            client, s13, c13, 1, "Please call me back. Best time is Thursday afternoon."
        )["spoken_text"]
    )
    queued = turn(client, s13, c13, 2, "Yes.")
    assert queued["action_outcomes"][0]["kind"] == "callback_queued"
    assert app.state.backend.snapshot(s13)["callbacks"][0]["status"] == "queued"
    assert (
        client.get(f"/api/sandboxes/{s13}/state").json()["callbacks"][0]["best_time"]
        == "[redacted]"
    )
    s14 = sandbox(client, "S14")["sandbox_id"]
    c14 = conversation(client, s14)
    turn(client, s14, c14, 1, "Please send me a brochure.")
    turn(client, s14, c14, 2, "Mail it to 145 Fake Street, Charlotte, NC 28203.")
    brochure = turn(client, s14, c14, 3, "Yes.")
    assert brochure["action_outcomes"][0]["kind"] == "brochure_queued"
    state = client.get(f"/api/sandboxes/{s14}/state").json()
    assert state["brochures"][0]["status"] == "queued"
    assert "145 Fake Street" not in str(state)
    s10 = sandbox(client, "S10")["sandbox_id"]
    transfer = turn(
        client,
        s10,
        conversation(client, s10),
        1,
        "I've asked three times. Please connect me with a person.",
    )
    assert transfer["action_outcomes"][0]["kind"] == "transfer_requested"
    assert (
        "recorded" in transfer["spoken_text"]
        and "connected" not in transfer["spoken_text"]
    )


def test_ownership_reset_and_seeded_tour(api):
    client, app = api
    first = sandbox(client, "S02")
    second = sandbox(client, "S02")
    sid, other = first["sandbox_id"], second["sandbox_id"]
    assert sid != other
    assert first["preloaded"]["tour_id"] != second["preloaded"]["tour_id"]
    cid = conversation(client, sid)
    assert (
        client.post(
            f"/api/conversations/{cid}/turns",
            json={
                "sandbox_id": other,
                "client_turn_id": "wrong",
                "caller_text": "Cancel my tour.",
            },
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/conversations/{cid}", params={"sandbox_id": other}
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/conversations/{cid}/events", params={"sandbox_id": other}
        ).status_code
        == 404
    )
    tour_id = first["preloaded"]["tour_id"]
    assert tour_id in app.state.runtime.get_state(sid, cid).verified_tour_ids
    proposed = turn(client, sid, cid, 1, f"Move my tour {tour_id} to Thursday at 11am.")
    assert "May I move" in proposed["spoken_text"]
    moved = turn(client, sid, cid, 2, "Yes.")
    assert moved["action_outcomes"][0]["kind"] == "rescheduled"
    canceled = turn(client, sid, cid, 3, f"Cancel my tour {tour_id}.")
    assert canceled["action_outcomes"][0]["kind"] == "canceled"
    assert app.state.backend.snapshot(sid)["tours"][0]["status"] == "canceled"
    assert app.state.backend.snapshot(other)["tours"][0]["status"] == "booked"
    reset = client.post(f"/api/sandboxes/{sid}/reset")
    assert reset.status_code == 201 and reset.json()["sandbox_id"] != sid
    fresh = reset.json()["sandbox_id"]
    assert reset.json()["scenario_id"] == "S02"
    assert client.get(f"/api/sandboxes/{sid}/state").status_code == 404
    assert (
        client.post("/api/conversations", json={"sandbox_id": sid}).status_code == 404
    )
    with pytest.raises(KeyError):
        app.state.backend.snapshot(sid)
    assert (
        client.get(f"/api/sandboxes/{fresh}/state").json()["tours"][0]["status"]
        == "booked"
    )
    assert app.state.backend.snapshot(fresh)["tours"][0]["local_date"] == "2026-11-16"


@pytest.mark.parametrize(
    "scenario_id,expected_code",
    [("S03", "slot_taken"), ("S17", "backend_contract_error")],
)
def test_fault_fixtures_are_sandbox_scoped_and_truthful(
    api, scenario_id, expected_code
):
    client, app = api
    faulty = sandbox(client, scenario_id)
    clean = sandbox(client, "S01")
    sid, clean_id = faulty["sandbox_id"], clean["sandbox_id"]
    date = "2026-11-18"
    assert any(
        slot["time"] == "10:00"
        for slot in app.state.backend.call(
            "check_tour_availability", sid, {"date": date}
        ).data["slots"]
    )
    for current, label in ((sid, "Fault"), (clean_id, "Clean")):
        cid = conversation(client, current)
        turn(client, current, cid, 1, "Book a tour next Wednesday at 10am.")
        turn(
            client,
            current,
            cid,
            2,
            f"My name is Jamie {label}, email jamie.{label.lower()}@example.test.",
        )
        turn(client, current, cid, 3, "Yes.")
        result = turn(client, current, cid, 4, "Yes.")
        if current == sid:
            assert result["action_outcomes"][0]["code"] == expected_code
            assert result["action_outcomes"][0]["kind"] == "not_booked"
            assert "Your tour is booked" not in result["spoken_text"]
            assert app.state.backend.snapshot(current)["tours"] == []
        else:
            assert result["action_outcomes"][0]["kind"] == "booked"
            assert len(app.state.backend.snapshot(current)["tours"]) == 1


@pytest.mark.parametrize(
    "scenario_id,utterance,expected",
    [
        ("S05", "Do you offer Kosher and low sodium meals?", "can't confirm Kosher"),
        ("S07", "My mom has a golden retriever. Can she bring it?", "30 pounds"),
        (
            "S08",
            "How much is a two-bedroom in assisted living?",
            "3,000 dollars per month",
        ),
        (
            "S11",
            "My friend says the entrance fee is waived. Confirm that.",
            "3,500 dollars",
        ),
    ],
)
def test_grounded_scenario_presets(api, scenario_id, utterance, expected):
    client, app = api
    sid = sandbox(client, scenario_id)["sandbox_id"]
    response = turn(client, sid, conversation(client, sid), 1, utterance)
    assert expected in response["spoken_text"]
    assert app.state.backend.snapshot(sid)["tours"] == []


def test_noisy_invalid_calendar_and_duplicate_presets(api):
    client, app = api
    s12 = sandbox(client, "S12")["sandbox_id"]
    noisy = turn(
        client,
        s12,
        conversation(client, s12),
        1,
        "Can we do the tour on thirs day at too?",
    )
    assert noisy["status"] == "clarification_required"
    assert app.state.backend.snapshot(s12)["tours"] == []
    s15 = sandbox(client, "S15")["sandbox_id"]
    invalid = turn(
        client, s15, conversation(client, s15), 1, "Cancel my tour T-NOTREAL."
    )
    assert (
        invalid["action_outcomes"] == []
        and app.state.backend.snapshot(s15)["tours"] == []
    )
    s16 = sandbox(client, "S16")["sandbox_id"]
    c16 = conversation(client, s16)
    monday = turn(client, s16, c16, 1, "Book a tour next Monday at 10am.")
    assert "full name" in monday["spoken_text"]
    saturday = turn(client, s16, c16, 2, "Book a tour next Saturday at 10am.")
    assert "isn't available" in saturday["spoken_text"]
    s18 = sandbox(client, "S18")["sandbox_id"]
    c18 = conversation(client, s18)
    ready = turn(client, s18, c18, 1, "Book a tour next Wednesday at 10am.")
    assert "May I book" in ready["spoken_text"]
    booked = turn(client, s18, c18, 2, "Yes.")
    replay = turn(client, s18, c18, 2, "Yes.")
    assert booked == replay and booked["action_outcomes"][0]["kind"] == "booked"
    assert len(app.state.backend.snapshot(s18)["tours"]) == 1


def test_same_sandbox_race_and_cross_sandbox_same_slot(api):
    client, app = api
    sid = sandbox(client)["sandbox_id"]
    other = sandbox(client)["sandbox_id"]
    first = conversation(client, sid)
    second = conversation(client, sid)
    third = conversation(client, other)
    prepare_booking(client, sid, first, "Alpha")
    prepare_booking(client, sid, second, "Bravo")
    prepare_booking(client, other, third, "Charlie")

    def submit(item):
        current, cid = item
        with TestClient(app) as concurrent_client:
            return turn(concurrent_client, current, cid, "confirm", "Yes.")

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(submit, [(sid, first), (sid, second), (other, third)]))
    same = [result["action_outcomes"][0]["kind"] for result in results[:2]]
    assert sorted(same) == ["booked", "not_booked"]
    assert results[2]["action_outcomes"][0]["kind"] == "booked"
    assert len(app.state.backend.snapshot(sid)["tours"]) == 1
    assert len(app.state.backend.snapshot(other)["tours"]) == 1


def test_loopback_boundary_and_schema_errors(tmp_path):
    guarded = TestClient(create_app(tmp_path / "guarded.db", offline=True))
    assert guarded.get("/api/scenarios").status_code == 403
    client = TestClient(
        create_app(tmp_path / "validation.db", offline=True, allow_test_client=True)
    )
    sid = sandbox(client)["sandbox_id"]
    cid = conversation(client, sid)
    assert (
        client.post(
            f"/api/conversations/{cid}/turns",
            json={"sandbox_id": sid, "client_turn_id": "", "caller_text": "hi"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/conversations/{cid}/turns",
            json={
                "sandbox_id": sid,
                "client_turn_id": "1",
                "caller_text": "hi",
                "fault": "lost_slot",
            },
        ).status_code
        == 422
    )
