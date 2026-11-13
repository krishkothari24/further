"""Deterministic safe fallback after a verified fact read."""

from .contracts import ToolResult


def speak_fact(topic: str, field: str, result: ToolResult) -> str:
    if not result.ok or not result.state_verified or not result.data:
        return "I don't have confirmed information about that. I can request staff follow-up."
    fact = result.data["fields"][field]
    if fact["status"] != "known":
        if field == "two_bedroom_assisted_living":
            return "I don't have a confirmed price for a two-bedroom in assisted living. A team member can check."
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
