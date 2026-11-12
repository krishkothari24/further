"""Small, conservative fact selector and spoken rendering from the canonical registry."""

import re

from .contracts import ToolResult


def fact_requests(text: str) -> list[tuple[str, str]]:
    words = text.lower().replace("-", " ")
    requests: list[tuple[str, str]] = []

    def add(topic: str, field: str) -> None:
        if (topic, field) not in requests:
            requests.append((topic, field))

    if (
        "entrance fee" in words
        or "move in fee" in words
        or re.search(r"\bfee\b", words)
    ):
        add("pricing", "entrance_fee")
    if re.search(r"\b(waiv|waiver|discount|remove the fee)", words):
        add("pricing", "entrance_fee_waiver")
    if "independent" in words and re.search(
        r"\b(price|cost|month|start|much)\b", words
    ):
        add("pricing", "independent_living_from")
    if "assisted" in words and re.search(r"\b(price|cost|month|start|much)\b", words):
        add("pricing", "assisted_living_from")
    if "two bedroom" in words or "2 bedroom" in words:
        add("pricing", "two_bedroom_assisted_living")
    if re.search(r"\b(price|cost|much)\b", words) and not any(
        field in words for field in ("independent", "assisted", "bedroom", "fee")
    ):
        add("pricing", "independent_living_from")
        add("pricing", "assisted_living_from")
        add("pricing", "entrance_fee")
    if re.search(r"\b(include|included|inclusions)\b", words) and re.search(
        r"\b(cost|price|monthly)\b", words
    ):
        add("pricing", "monthly_inclusions")
    if re.search(r"\b(golden retriever|dog|pet)\b", words):
        add("pets", "dog_weight_limit_lbs")
    if "kosher" in words:
        add("dietary", "kosher")
    if "low sodium" in words:
        add("dietary", "low_sodium")
    if "dementia" in words or "memory care" in words:
        add("memory_care", "offered")
        add("memory_care", "dementia_suitability")
    if (
        re.search(r"\b(couple|couples|spouse|husband|wife|parents)\b", words)
        or "mom and dad" in words
        or "live together" in words
    ):
        add("care_types", "couples_policy")
    if (
        "thermostat" in words
        or (
            "air conditioning" in words
            and re.search(
                r"\b(individual|individually|control|controlled|set|adjust)\b", words
            )
        )
        or (
            "temperature" in words
            and re.search(r"\b(control|controlled|set|adjust)\b", words)
        )
    ):
        add("room_types", "individual_thermostat")
    elif "air conditioning" in words or "a/c" in words:
        add("room_types", "general_air_conditioning")
    if re.search(r"\b(car|cars|parking)\b", words):
        add("parking", "resident_cars")
    if "gym" in words:
        add("amenities", "gym")
    if "elevator" in words:
        add("amenities", "elevators")
    if "amenit" in words and "gym" not in words and "elevator" not in words:
        add("amenities", "gym")
        add("amenities", "elevators")
    if "medicaid" in words:
        add("funding", "medicaid_eligibility")
    if "hiring" in words or "jobs" in words:
        add("careers", "current_openings")
    if re.search(
        r"\b(phone number|your number|community number|contact number)\b", words
    ):
        add("phone", "main")
    return requests


def speak_fact(topic: str, field: str, result: ToolResult) -> str:
    if not result.ok or not result.state_verified or not result.data:
        return "I don't have confirmed information about that. I can request staff follow-up."
    fact = result.data["fields"][field]
    if fact["status"] != "known":
        if field == "entrance_fee_waiver":
            return "I can't confirm an entrance fee waiver. A team member can discuss that request."
        if field == "kosher":
            return "I can't confirm Kosher meals. A team member can check."
        if field == "dementia_suitability":
            return "I can't assess whether this community would meet someone's dementia care needs. Staff can discuss care needs."
        if field == "couples_policy":
            return "I can't confirm arrangements for couples. A team member can discuss your situation."
        if field == "monthly_inclusions":
            return "I don't have a confirmed list of what monthly pricing includes. A team member can explain."
        if field == "individual_thermostat":
            return "I can't confirm individual room temperature controls. A team member can check."
        if field == "general_air_conditioning":
            return "I can't confirm room air conditioning from the current catalog. A team member can check."
        if field == "resident_cars":
            return "I can't confirm the resident car policy. A team member can check."
        return "I don't have confirmed information about that. A team member can check."
    value = fact["value"]
    if (topic, field) == ("pricing", "entrance_fee"):
        return f"The entrance fee is {value:,} dollars."
    if field in {"independent_living_from", "assisted_living_from"}:
        label = (
            "Independent living"
            if field.startswith("independent")
            else "Assisted living"
        )
        return f"{label} starts at {value:,} dollars per month."
    if (topic, field) == ("pets", "dog_weight_limit_lbs"):
        return f"Dogs are allowed up to {value} pounds. I would need your dog's weight to check the policy."
    if (topic, field) == ("memory_care", "offered"):
        return (
            "The community does not offer dedicated memory care."
            if value is False
            else "The community offers memory care."
        )
    if (topic, field) == ("dietary", "low_sodium"):
        return (
            "Low sodium meals are listed as an option."
            if value
            else "Low sodium meals are not listed."
        )
    if (topic, field) == ("phone", "main"):
        return f"Our phone number is {value}."
    if isinstance(value, bool):
        return f"The catalog lists {field.replace('_', ' ')} as {'available' if value else 'unavailable'}."
    return f"The catalog lists {value}."
