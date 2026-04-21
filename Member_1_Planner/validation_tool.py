"""Validation tool used by the Planner Agent."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field
from requests import RequestException

from Member_2_Researcher.attraction_tool import resolve_destination

KNOWN_NON_SRI_LANKAN_DESTINATIONS = {
    "tokyo",
    "paris",
    "london",
    "singapore",
    "bangkok",
    "new york",
    "dubai",
    "rome",
    "seoul",
    "kuala lumpur",
    "sydney",
    "melbourne",
    "delhi",
    "mumbai",
    "beijing",
    "shanghai",
    "maldives",
    "india",
    "japan",
    "france",
    "england",
    "thailand",
    "uae",
    "united arab emirates",
}


class PlannerRequestInput(BaseModel):
    """Structured request extracted from a natural-language trip prompt."""

    destination: str
    days: int = Field(gt=0)
    budget: float = Field(gt=0)
    currency: str = "LKR"
    interests: list[str]


class PlannerValidationResult(BaseModel):
    """Structured output returned by the planner validation tool."""

    normalized_destination: str
    currency: str
    normalized_interests: list[str]
    budget_tier: Literal["low", "medium", "high"]
    daily_trip_pacing: Literal["relaxed", "balanced", "packed"]
    warnings: list[str]
    planning_constraints: list[str]


class PlannerTaskContext(BaseModel):
    """Structured context used to build downstream planner tasks."""

    normalized_destination: str
    normalized_interests: list[str]
    days: int = Field(gt=0)
    budget_tier: Literal["low", "medium", "high"]
    daily_trip_pacing: Literal["relaxed", "balanced", "packed"]
    warnings: list[str]


def parse_trip_request(request: str) -> PlannerRequestInput:
    """Parse a controlled natural-language travel request into structured fields.

    Example:
        "Plan a 2-day trip to Kandy under 30000 for culture and food"

    Notes:
        This parser intentionally supports a narrow, semi-structured request style
        for predictable local execution. It is not intended to handle every possible
        natural-language phrasing.
    """
    cleaned_request = request.strip()
    if not cleaned_request:
        raise ValueError("Request text is required.")

    days_match = re.search(r"(\d+)\s*-\s*day|(\d+)\s*day", cleaned_request, flags=re.IGNORECASE)
    if not days_match:
        raise ValueError("Could not find the number of days in the request.")
    days = int(next(group for group in days_match.groups() if group))

    destination_match = re.search(
        r"(?:trip|travel)\s+to\s+([A-Za-z\s]+?)(?:\s+under\s+(?:[A-Za-z]{2,4}\s+|Rs\.?\s*)?\d+|\s+for\s+.+|$)",
        cleaned_request,
        flags=re.IGNORECASE,
    )
    if not destination_match:
        raise ValueError("Could not find the destination in the request.")
    destination = destination_match.group(1).strip()

    budget_match = re.search(
        r"under\s+(?:(LKR|USD|EUR|GBP|Rs\.?)\s*)?(\d+(?:\.\d+)?)",
        cleaned_request,
        flags=re.IGNORECASE,
    )
    if not budget_match:
        raise ValueError("Could not find the budget in the request.")
    raw_currency = budget_match.group(1) or "LKR"
    currency = _normalize_currency(raw_currency)
    budget = float(budget_match.group(2))

    interests_match = re.search(r"\sfor\s+(.+)$", cleaned_request, flags=re.IGNORECASE)
    interests_text = interests_match.group(1).strip() if interests_match else ""
    interests = _split_interests(interests_text)

    return PlannerRequestInput(
        destination=destination,
        days=days,
        budget=budget,
        currency=currency,
        interests=interests,
    )


def create_trip_tasks(context: PlannerTaskContext) -> list[str]:
    """Create downstream task assignments for the planner workflow.

    Args:
        context: Normalized planning context from the planner validation stage.

    Returns:
        A task list that the Planner Agent can pass to other agents.
    """
    joined_interests = ", ".join(context.normalized_interests)
    tasks = [
        (
            f"Researcher: find attractions and activities in {context.normalized_destination} "
            f"for {context.days} day(s) matching these interests: {joined_interests}."
        ),
        (
            "Executor: estimate accommodation, food, transport, and attraction costs "
            f"for a {context.budget_tier} budget trip."
        ),
        (
            "Reviewer: verify that the plan is complete, realistic, and aligned with the user's budget "
            f"and {context.daily_trip_pacing} pace."
        ),
    ]

    if context.budget_tier == "low":
        tasks.append("Executor: prioritize low-cost and free options where possible.")
    if context.warnings:
        tasks.append("Reviewer: pay extra attention to risks flagged by the planner validation stage.")

    return tasks


def validate_and_structure_trip_request(
    destination: str,
    budget: float,
    days: int,
    interests: list[str],
    currency: str = "LKR",
) -> PlannerValidationResult:
    """Validate and normalize the user request for downstream agents.

    Args:
        destination: Requested trip destination.
        budget: Total user budget for the trip.
        days: Number of days in the trip.
        interests: User interests that should guide itinerary creation.
        currency: Currency code used for the budget.

    Returns:
        A strictly structured planning payload for the Planner Agent.

    Raises:
        ValueError: If the request is missing required values or contains invalid values.
    """
    normalized_destination = destination.strip()
    if not normalized_destination:
        raise ValueError("Destination is required.")
    _ensure_sri_lanka_destination(normalized_destination)
    if budget <= 0:
        raise ValueError("Budget must be greater than zero.")
    if days <= 0:
        raise ValueError("Days must be greater than zero.")
    if days > 14:
        raise ValueError("Days must be 14 or fewer for this project scope.")

    normalized_interests = _normalize_interests(interests)
    normalized_currency = currency.strip().upper() or "LKR"
    budget_tier = _classify_budget_tier(budget, days, normalized_currency)
    daily_trip_pacing = _classify_trip_pacing(days, len(normalized_interests))
    warnings = _build_warnings(normalized_destination, budget, days, normalized_interests, budget_tier, daily_trip_pacing)
    planning_constraints = _build_constraints(budget_tier, daily_trip_pacing, days, normalized_interests)

    return PlannerValidationResult(
        normalized_destination=normalized_destination,
        currency=normalized_currency,
        normalized_interests=normalized_interests,
        budget_tier=budget_tier,
        daily_trip_pacing=daily_trip_pacing,
        warnings=warnings,
        planning_constraints=planning_constraints,
    )


def _ensure_sri_lanka_destination(destination: str) -> None:
    """Reject destinations outside Sri Lanka before downstream planning begins.

    The Planner is intentionally scoped to Sri Lankan travel planning. This
    check reuses the shared destination resolver so unsupported locations are
    blocked early and the rest of the workflow receives only local destinations.
    """
    lowered_destination = destination.strip().lower()
    if lowered_destination in KNOWN_NON_SRI_LANKAN_DESTINATIONS:
        raise ValueError(
            f"Destination '{destination}' is outside Sri Lanka. This planner currently supports Sri Lanka destinations only."
        )

    try:
        resolve_destination(destination, timeout=10)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    except RequestException as exc:
        raise ValueError(
            "Could not verify that the destination is in Sri Lanka. Please try again."
        ) from exc


def _split_interests(interests_text: str) -> list[str]:
    """Split a free-text interest segment into normalized interest labels."""
    parts = re.split(r",| and ", interests_text, flags=re.IGNORECASE)
    interests = [part.strip().lower() for part in parts if part.strip()]
    return interests or ["general sightseeing"]


def _normalize_currency(raw_currency: str) -> str:
    """Normalize parsed currency tokens into a consistent uppercase code."""
    lowered = raw_currency.strip().lower().replace(".", "")
    if lowered == "rs":
        return "LKR"
    return lowered.upper()


def _normalize_interests(interests: list[str]) -> list[str]:
    """Normalize interests to lowercase unique labels while preserving order."""
    cleaned: list[str] = []
    for interest in interests:
        normalized = interest.strip().lower()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned or ["general sightseeing"]


def _classify_budget_tier(budget: float, days: int, currency: str) -> Literal["low", "medium", "high"]:
    """Classify budget tier using simple heuristic per-day thresholds.

    Notes:
        These thresholds are demo heuristics intended for project evaluation and
        should be calibrated per currency or destination in future work.
    """
    if currency == "LKR":
        if budget < 10000:
            return "low"
        if budget > 100000:
            return "high"
        return "medium"

    per_day = budget / days
    if per_day < 60:
        return "low"
    if per_day < 180:
        return "medium"
    return "high"


def _classify_trip_pacing(days: int, interest_count: int) -> Literal["relaxed", "balanced", "packed"]:
    """Infer itinerary pacing from trip length and breadth of interests."""
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
    budget_tier: Literal["low", "medium", "high"],
    daily_trip_pacing: Literal["relaxed", "balanced", "packed"],
) -> list[str]:
    """Build planner warnings for unrealistic, risky, or expensive requests."""
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


def _build_constraints(
    budget_tier: Literal["low", "medium", "high"],
    daily_trip_pacing: Literal["relaxed", "balanced", "packed"],
    days: int,
    interests: list[str],
) -> list[str]:
    """Build downstream planning constraints from validated planner context."""
    constraints = [
        f"Plan for exactly {days} travel day(s).",
        f"Use a {daily_trip_pacing} itinerary pace.",
        "Do not invent attractions, prices, or transport options in the planner stage.",
        "Ensure the Researcher matches attractions to the user's interests.",
        "Ensure the Executor evaluates accommodation, food, transport, and attraction costs.",
        "Ensure the Reviewer checks completeness, realism, and budget fit before approval.",
    ]
    if budget_tier == "low":
        constraints.append("Prefer free or low-cost attractions and budget-friendly food and transport assumptions.")
    if "food" in interests:
        constraints.append("Reserve space for food-related recommendations in the itinerary.")
    if "anime" in interests:
        constraints.append("Ensure the research stage includes anime-related locations if available.")
    return constraints
