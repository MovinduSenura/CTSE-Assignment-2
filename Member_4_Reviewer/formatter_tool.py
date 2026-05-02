"""Formatting, auditing, and validation tools for the Reviewer Agent.

This module provides deterministic helper tools that the Reviewer Agent
uses to evaluate itinerary quality before the LLM review step and to
build fallback itinerary output when the LLM produces weak results.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuditResult(BaseModel):
    """Structured result of the itinerary quality audit.

    Attributes:
        warnings: Quality issues that should be flagged to the user.
        suggestions: Non-critical improvement ideas for the travel plan.
        completeness_score: Overall itinerary quality score between 0.0 and 1.0.
        interest_coverage: Fraction of user interests matched by attractions.
        budget_aligned: Whether the estimated cost is within the user budget.
        has_enough_attractions: Whether there are enough attractions for the trip days.
    """

    warnings: list[str]
    suggestions: list[str]
    completeness_score: float = Field(ge=0.0, le=1.0)
    interest_coverage: float = Field(ge=0.0, le=1.0)
    budget_aligned: bool
    has_enough_attractions: bool


class ItineraryValidationResult(BaseModel):
    """Structured result of itinerary text validation.

    Attributes:
        is_valid: Whether the itinerary passes all structural checks.
        issues: Specific structural problems found.
        has_overview: Whether the text contains an overview section.
        has_day_markers: Whether the text contains day-by-day markers.
        has_budget_summary: Whether the text contains a budget summary section.
        day_marker_count: Number of distinct Day N markers found.
    """

    is_valid: bool
    issues: list[str]
    has_overview: bool
    has_day_markers: bool
    has_budget_summary: bool
    day_marker_count: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Audit tool
# ---------------------------------------------------------------------------

def audit_itinerary(
    research_output: dict,
    budget_output: dict,
    days: int,
    interests: list[str] | None = None,
    budget_limit: float | None = None,
) -> AuditResult:
    """Perform a quality audit on the assembled itinerary data.

    This tool checks whether the travel plan is complete, realistic, and
    aligned with the user's constraints before the LLM produces the final
    review.  It returns structured findings so the Reviewer Agent can make
    deterministic decisions.

    Args:
        research_output: Structured output from the Researcher Agent containing
            destination_summary and attractions.
        budget_output: Structured output from the Executor Agent containing
            currency, line_items, total_estimated_cost, budget_status, and summary.
        days: Number of requested trip days.
        interests: User interests for interest-coverage analysis.  Defaults to
            None which skips interest coverage checks.
        budget_limit: User maximum budget for utilization analysis.  Defaults to
            None which skips utilization checks.

    Returns:
        An AuditResult with warnings, suggestions, completeness score,
        interest coverage, and budget alignment status.

    Raises:
        ValueError: If days is not positive or required dict keys are missing.
    """
    if days <= 0:
        raise ValueError("Days must be a positive integer for audit.")
    if "attractions" not in research_output:
        raise ValueError("research_output must contain 'attractions' key.")
    if "budget_status" not in budget_output:
        raise ValueError("budget_output must contain 'budget_status' key.")

    warnings: list[str] = []
    suggestions: list[str] = []
    score = 1.0

    attractions = research_output.get("attractions", [])
    destination_summary = research_output.get("destination_summary", "").strip()
    budget_status = budget_output.get("budget_status", "unknown")
    total_cost = budget_output.get("total_estimated_cost", 0.0)

    # Check 1: Enough attractions for the trip
    has_enough = len(attractions) >= days
    if not has_enough:
        warnings.append(
            "Not enough attractions were found to comfortably fill "
            "the requested number of days."
        )
        score -= 0.20

    # Check 2: Budget alignment
    budget_aligned = budget_status != "over budget"
    if not budget_aligned:
        warnings.append("Estimated trip cost is above the user's budget.")
        score -= 0.20

    # Check 3: Destination summary presence
    if not destination_summary:
        warnings.append("Destination summary is missing from research output.")
        score -= 0.15

    # Check 4: Interest coverage
    interest_coverage = _compute_interest_coverage(attractions, interests)
    if interests and interest_coverage < 0.5:
        warnings.append(
            f"Only {interest_coverage:.0%} of requested interests are covered "
            f"by the recommended attractions."
        )
        score -= 0.15

    # Check 5: Pacing — too many attractions per day
    if days > 0 and len(attractions) > days * 3:
        warnings.append(
            "The number of recommended attractions may lead to an "
            "overpacked itinerary."
        )
        suggestions.append("Consider limiting attractions to 2-3 per day.")
        score -= 0.10

    # Check 6: Missing source URLs
    missing_sources = sum(
        1 for a in attractions if not a.get("source", "").strip()
    )
    if missing_sources > 0:
        suggestions.append(
            f"{missing_sources} attraction(s) are missing source references."
        )
        score -= 0.05

    # Check 7: Budget utilization
    if budget_limit and budget_limit > 0 and total_cost > 0:
        utilization = total_cost / budget_limit
        if utilization < 0.15:
            suggestions.append(
                f"Budget utilization is very low ({utilization:.0%}). "
                f"Consider upgrading accommodation or adding activities."
            )
        elif utilization > 0.90 and budget_aligned:
            suggestions.append(
                "Budget utilization is high. Leave a small buffer for "
                "unexpected expenses."
            )

    completeness_score = round(max(0.0, min(1.0, score)), 2)

    return AuditResult(
        warnings=warnings,
        suggestions=suggestions,
        completeness_score=completeness_score,
        interest_coverage=round(interest_coverage, 2),
        budget_aligned=budget_aligned,
        has_enough_attractions=has_enough,
    )


# ---------------------------------------------------------------------------
# Itinerary text validator
# ---------------------------------------------------------------------------

def validate_itinerary_text(
    itinerary: str,
    days: int,
) -> ItineraryValidationResult:
    """Validate the structural integrity of a formatted itinerary string.

    This tool performs deterministic checks on the final itinerary text to
    ensure it meets the required format before being presented to the user.

    Args:
        itinerary: The formatted itinerary text to validate.
        days: The expected number of trip days.

    Returns:
        An ItineraryValidationResult describing whether the itinerary is
        structurally valid and listing any issues found.

    Raises:
        ValueError: If days is not a positive integer.
    """
    if days <= 0:
        raise ValueError("Days must be a positive integer for validation.")

    issues: list[str] = []
    text = itinerary.strip()

    if len(text) < 100:
        issues.append("Itinerary text is too short to be a complete plan.")

    first_line = text.split("\n")[0] if text else ""
    has_overview = (
        "overview" in text.lower()
        or "Travel Plan" in first_line
        or "Plan" in first_line
    )
    if not has_overview:
        issues.append("Itinerary is missing an overview section.")

    day_marker_count = sum(
        1 for d in range(1, days + 1) if f"Day {d}" in text
    )
    has_day_markers = day_marker_count >= min(days, 1)
    if not has_day_markers:
        issues.append(
            f"Expected {days} 'Day N' labels, found {day_marker_count}."
        )
    elif day_marker_count < days:
        issues.append(
            f"Itinerary has only {day_marker_count} of {days} "
            f"expected day markers."
        )

    has_budget_summary = "Budget Summary" in text
    if not has_budget_summary:
        issues.append("Itinerary is missing a 'Budget Summary' section.")

    return ItineraryValidationResult(
        is_valid=len(issues) == 0,
        issues=issues,
        has_overview=has_overview,
        has_day_markers=has_day_markers,
        has_budget_summary=has_budget_summary,
        day_marker_count=day_marker_count,
    )


# ---------------------------------------------------------------------------
# Deterministic itinerary formatter (fallback)
# ---------------------------------------------------------------------------

def format_final_itinerary(
    destination: str,
    days: int,
    user_goal: str,
    attractions: list[dict],
    budget_output: dict,
    budget_summary: str,
    warnings: list[str],
    suggestions: list[str] | None = None,
) -> str:
    """Create a deterministic, readable itinerary string.

    This is the fallback formatter used when the LLM does not produce a
    structurally valid itinerary.  It guarantees that the user receives a
    usable travel plan with day-by-day sections and a budget summary.

    Args:
        destination: Trip destination name.
        days: Number of trip days.
        user_goal: The user's stated travel goal from the Planner output.
        attractions: List of attraction dicts, each containing name,
            description, estimated_time_hours, interest_match, and source.
        budget_output: Full budget output dict from the Executor Agent,
            used for the budget breakdown section.
        budget_summary: Budget summary string from the Executor output.
        warnings: Audit warnings to include in the output.
        suggestions: Optional improvement suggestions to include.

    Returns:
        A formatted multi-line itinerary string ready for user display.

    Raises:
        ValueError: If destination is empty, days is not positive, or
            attractions list is empty.
    """
    if not destination or not destination.strip():
        raise ValueError("Destination is required for itinerary formatting.")
    if days <= 0:
        raise ValueError("Days must be a positive integer.")
    if not attractions:
        raise ValueError(
            "At least one attraction is required to build an itinerary."
        )

    lines: list[str] = [
        f"{destination} {days}-Day Travel Plan",
        "",
        f"Overview: {user_goal}",
        "",
    ]

    for day in range(days):
        attraction = attractions[day % len(attractions)]
        lines.append(
            f"Day {day + 1}: Visit {attraction['name']} "
            f"for about {attraction['estimated_time_hours']} hours. "
            f"Focus: {attraction['interest_match']}. "
            f"{attraction['description']}"
        )

    lines.extend(["", f"Budget Summary: {budget_summary}"])

    # Budget breakdown from executor line items
    line_items = budget_output.get("line_items", [])
    if line_items:
        lines.append("")
        lines.append("Budget Breakdown:")
        for item in line_items:
            category = item.get("category", "Unknown")
            amount = item.get("amount", 0)
            reasoning = item.get("reasoning", "")
            lines.append(
                f"- {category}: {budget_output.get('currency', '')} "
                f"{amount:.2f} ({reasoning})"
            )

    lines.extend(["", "Recommended attractions:"])
    for attraction in attractions[: min(len(attractions), days * 2)]:
        lines.append(f"- {attraction['name']} ({attraction['source']})")

    if warnings:
        lines.extend(["", "Warnings:"])
        for warning in warnings:
            lines.append(f"- {warning}")

    if suggestions:
        lines.extend(["", "Suggestions:"])
        for suggestion in suggestions:
            lines.append(f"- {suggestion}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_interest_coverage(
    attractions: list[dict],
    interests: list[str] | None,
) -> float:
    """Compute the fraction of user interests matched by attractions.

    Args:
        attractions: List of attraction dicts with interest_match fields.
        interests: List of user interest strings.

    Returns:
        A float between 0.0 and 1.0 representing interest coverage.
    """
    if not interests:
        return 1.0
    user_interests = {
        interest.strip().lower()
        for interest in interests
        if interest.strip()
    }
    if not user_interests:
        return 1.0
    matched: set[str] = set()
    for attraction in attractions:
        match = attraction.get("interest_match", "").strip().lower()
        if match in user_interests:
            matched.add(match)
    return len(matched) / len(user_interests)
