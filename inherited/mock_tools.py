"""Mock backend for the ACME Senior Living voice agent. State is in memory and resets on restart."""
import uuid
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

COMMUNITY_TZ = ZoneInfo("America/New_York")
OPEN_HOUR, CLOSE_HOUR = 9, 18  # tours run Monday to Friday, 9am to 6pm

TOURS: dict[str, dict] = {}
LEADS: dict[str, dict] = {}
CALLBACKS: list[dict] = []
TRANSFERS: list[dict] = []
BROCHURES: list[dict] = []

COMMUNITY_INFO = {
    "pricing": {"independent_living_from": 2000, "assisted_living_from": 3000, "entrance_fee": 3500},
    "care_types": ["Independent Living", "Assisted Living"],
    "memory_care": False,
    "pets": {"cats": True, "dogs": True, "dog_weight_limit_lbs": 30, "service_animals": True},
    "room_types": ["Studio", "1 Bedroom / 1 Bath", "2 Bedroom / 1.5 Bath"],
    "phone": "850-445-8362",
    "address": "145 Fake Street, Charlotte, NC 28203",
}

def _is_open_day(day: date) -> bool:
    return day.weekday() not in (0, 6)  # 0 = Sunday, 6 = Saturday

def _is_taken(day: date, hour: int) -> bool:
    if day.weekday() == 1 and hour == 14:  # standing Tuesday 2pm staff meeting
        return True
    return any(t["date"] == day.isoformat() and t["hour"] == hour and t["status"] == "booked" for t in TOURS.values())

def check_tour_availability(date: str) -> dict:
    day = datetime.strptime(date, "%Y-%m-%d").date()
    if not _is_open_day(day):
        return {"date": date, "slots": []}
    slots = []
    for hour in range(OPEN_HOUR, CLOSE_HOUR + 1):
        if _is_taken(day, hour):
            continue
        local = datetime.combine(day, time(hour), tzinfo=COMMUNITY_TZ)
        slots.append(local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S"))
    return {"date": date, "slots": slots}

def book_tour(date: str, time: str, first_name: str, last_name: str = "", phone: str = "", party_size: int = 1) -> dict:
    hour = datetime.strptime(time, "%H:%M").hour
    day = datetime.strptime(date, "%Y-%m-%d").date()
    if day.weekday() == 2 and hour == 10:  # another agent grabbed this slot a moment ago
        return {"success": True, "confirmation_id": None, "error": "slot_taken"}
    confirmation_id = "T-" + uuid.uuid4().hex[:6].upper()
    TOURS[confirmation_id] = {
        "date": date, "hour": hour, "first_name": first_name, "last_name": last_name,
        "phone": phone, "party_size": party_size, "status": "booked",
    }
    return {"success": True, "confirmation_id": confirmation_id}

def reschedule_tour(confirmation_id: str, date: str, time: str) -> dict:
    tour = TOURS.get(confirmation_id)
    if tour is None:
        return {"success": False, "error": "not_found"}
    tour["date"], tour["hour"] = date, datetime.strptime(time, "%H:%M").hour
    return {"success": True, "confirmation_id": confirmation_id}

def cancel_tour(confirmation_id: str) -> dict:
    TOURS.get(confirmation_id, {})["status"] = "cancelled"
    return {"success": True}

def get_community_info(topic: str) -> dict:
    return {"topic": topic, "info": COMMUNITY_INFO.get(topic, {})}

def upsert_lead(first_name: str = "", last_name: str = "", phone: str = "", email: str = "", notes: str = "") -> dict:
    lead_id = next((k for k, v in LEADS.items() if phone and v["phone"] == phone), None) or "L-" + uuid.uuid4().hex[:6].upper()
    LEADS[lead_id] = {"first_name": first_name, "last_name": last_name, "phone": phone, "email": email, "notes": notes}
    return {"lead_id": lead_id}

def schedule_callback(lead_id: str, best_time: str) -> dict:
    CALLBACKS.append({"lead_id": lead_id, "best_time": best_time})
    return {"success": True}

def transfer_to_human(reason: str) -> dict:
    TRANSFERS.append({"reason": reason})
    return {"success": True, "status": "transferring"}

def send_brochure(lead_id: str, address: str) -> dict:
    BROCHURES.append({"lead_id": lead_id, "address": address})
    return {"success": True}
