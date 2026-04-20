"""Budget calculation tool."""

from __future__ import annotations

import json
from pathlib import Path


DATA_PATH = Path(__file__).with_name("destinations.json")


def estimate_trip_budget(
    destination_context: dict,
    days: int,
    budget_limit: float,
    attraction_count: int,
    currency: str = "USD",
) -> dict:
    """Estimate a trip budget using destination profiles."""
    profiles = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    profile = profiles.get(destination_context["country"], profiles["DEFAULT"])

    hotel_total = round(profile["hotel_per_night"] * max(days - 1, 1), 2)
    food_total = round(profile["food_per_day"] * days, 2)
    transport_total = round(profile["transport_per_day"] * days, 2)
    attraction_total = round(profile["attraction_per_place"] * attraction_count, 2)

    line_items = [
        {"category": "Accommodation", "amount": hotel_total, "reasoning": "Nightly hotel estimate by destination profile."},
        {"category": "Food", "amount": food_total, "reasoning": "Average daily meals estimate."},
        {"category": "Transport", "amount": transport_total, "reasoning": "Local transport estimate for intra-city travel."},
        {"category": "Attractions", "amount": attraction_total, "reasoning": "Ticket buffer based on number of recommended places."},
    ]

    total = round(sum(item["amount"] for item in line_items), 2)
    status = "within budget" if total <= budget_limit else "over budget"
    summary = (
        f"Estimated {currency} {total:.2f} for {days} days in {destination_context['destination']}. "
        f"The trip is {status} against the user budget of {currency} {budget_limit:.2f}."
    )

    return {
        "currency": currency,
        "line_items": line_items,
        "total_estimated_cost": total,
        "budget_status": status,
        "summary": summary,
    }

