"""Validation tool used by the Planner Agent."""

from __future__ import annotations


def validate_and_structure_trip_request(
    destination: str,
    budget: float,
    days: int,
    interests: list[str],
) -> dict:
    """Validate and normalize the user request into planning constraints."""
    normalized_destination = destination.strip()
    if not normalized_destination:
        raise ValueError("Destination is required.")
    if budget <= 0:
        raise ValueError("Budget must be greater than zero.")
    if days <= 0:
        raise ValueError("Days must be greater than zero.")
    if days > 14:
        raise ValueError("Days must be 14 or fewer for this project scope.")

    normalized_interests = _normalize_interests(interests)
    budget_tier = _classify_budget_tier(budget, days)
    daily_trip_pacing = _classify_trip_pacing(days, len(normalized_interests))
    warnings = _build_warnings(normalized_destination, budget, days, normalized_interests, budget_tier, daily_trip_pacing)
    planning_constraints = _build_constraints(budget_tier, daily_trip_pacing, days, normalized_interests)

    return {
        "normalized_destination": normalized_destination,
        "normalized_interests": normalized_interests,
        "budget_tier": budget_tier,
        "daily_trip_pacing": daily_trip_pacing,
        "warnings": warnings,
        "planning_constraints": planning_constraints,
    }


def _normalize_interests(interests: list[str]) -> list[str]:
    cleaned: list[str] = []
    for interest in interests:
        normalized = interest.strip().lower()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned or ["general sightseeing"]


def _classify_budget_tier(budget: float, days: int) -> str:
    per_day = budget / days
    if per_day < 60:
        return "low"
    if per_day < 180:
        return "medium"
    return "high"


def _classify_trip_pacing(days: int, interest_count: int) -> str:
    if interest_count < max(days, 1):
        return "relaxed"
    if interest_count <= days * 2:
        return "balanced"
    return "packed"


def _build_warnings(
    destination: str,
    budget: float,
    days: int,
    interests: list[str],
    budget_tier: str,
    daily_trip_pacing: str,
) -> list[str]:
    warnings: list[str] = []
    if len(interests) >= days * 2 and days <= 3:
        warnings.append("The request includes many interests for a short trip, so prioritization is required.")
    if budget_tier == "low":
        warnings.append("The budget is tight, so paid attractions and premium accommodation should be minimized.")
    if destination.lower() in {"tokyo", "singapore", "paris", "london", "new york"} and budget / days < 100:
        warnings.append("The destination is typically expensive relative to the budget provided.")
    if daily_trip_pacing == "packed":
        warnings.append("The itinerary may become rushed unless activities are limited per day.")
    return warnings


def _build_constraints(budget_tier: str, daily_trip_pacing: str, days: int, interests: list[str]) -> list[str]:
    constraints = [
        f"Plan for exactly {days} travel day(s).",
        f"Use a {daily_trip_pacing} itinerary pace.",
        "Do not invent attractions, prices, or transport options in the planner stage.",
        "Ensure the research agent matches attractions to the user's interests.",
        "Ensure the budget agent evaluates accommodation, food, transport, and attraction costs.",
    ]
    if budget_tier == "low":
        constraints.append("Prefer free or low-cost attractions and budget-friendly food and transport assumptions.")
    if "food" in interests:
        constraints.append("Reserve space for food-related recommendations in the itinerary.")
    if "anime" in interests:
        constraints.append("Ensure the research stage includes anime-related locations if available.")
    return constraints

