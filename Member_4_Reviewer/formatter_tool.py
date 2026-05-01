"""Formatting and review helper tools."""

from __future__ import annotations


def audit_itinerary(research_output: dict, budget_output: dict, days: int) -> list[str]:
    """Check if the itinerary is realistic and complete."""
    warnings: list[str] = []
    if len(research_output["attractions"]) < days:
        warnings.append("Not enough attractions were found to comfortably fill the requested number of days.")
    if budget_output["budget_status"] == "over budget":
        warnings.append("Estimated trip cost is above the user's budget.")
    if not research_output["destination_summary"].strip():
        warnings.append("Destination summary is missing.")
    return warnings


def format_final_itinerary(
    destination: str,
    days: int,
    user_goal: str,
    attractions: list[dict],
    budget_output: dict,
    budget_summary: str,
    warnings: list[str],
) -> str:
    """Create a readable itinerary string."""
    lines = [
        f"{destination} {days}-Day Travel Plan",
        "",
        f"Overview: {user_goal}",
        "",
    ]

    for day in range(days):
        attraction = attractions[day % len(attractions)]
        lines.append(
            f"Day {day + 1}: Visit {attraction['name']} for about {attraction['estimated_time_hours']} hours. "
            f"Focus: {attraction['interest_match']}. {attraction['description']}"
        )

    lines.extend(["", f"Budget Summary: {budget_summary}"])

    line_items = budget_output.get("line_items", [])
    if line_items:
        lines.append("")
        lines.append("Budget Breakdown:")
        for item in line_items:
            category = item.get("category", "Unknown")
            amount = item.get("amount", 0)
            reasoning = item.get("reasoning", "")
            lines.append(f"- {category}: {budget_output.get('currency', '')} {amount:.2f} ({reasoning})")

    lines.extend(["", "Recommended attractions:"])
    for attraction in attractions[: min(len(attractions), days * 2)]:
        lines.append(f"- {attraction['name']} ({attraction['source']})")

    if warnings:
        lines.extend(["", "Warnings:"])
        for warning in warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines)

