"""Standalone evaluation harness for the Reviewer member's contribution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Member_4_Reviewer.formatter_tool import (
    audit_itinerary,
    format_final_itinerary,
    validate_itinerary_text,
)
from Member_4_Reviewer.reviewer_agent import ReviewerOutput


def evaluate_reviewer_pipeline() -> None:
    """Run deterministic checks for reviewer auditing, formatting, and validation."""

    # --- Audit tool checks ---
    research_output = {
        "destination_summary": "Kandy is a cultural city in Sri Lanka.",
        "attractions": [
            {
                "name": "Temple of the Tooth",
                "description": "Historic religious site.",
                "estimated_time_hours": 2.0,
                "interest_match": "culture",
                "source": "https://en.wikipedia.org/wiki/Temple_of_the_Tooth",
            },
            {
                "name": "Kandy Lake",
                "description": "Scenic lake in the city centre.",
                "estimated_time_hours": 1.5,
                "interest_match": "nature",
                "source": "https://en.wikipedia.org/wiki/Kandy_Lake",
            },
        ],
    }
    budget_output = {
        "currency": "LKR",
        "line_items": [
            {"category": "Accommodation", "amount": 55.0, "reasoning": "test"},
            {"category": "Food", "amount": 28.0, "reasoning": "test"},
            {"category": "Transport", "amount": 16.0, "reasoning": "test"},
            {"category": "Attractions", "amount": 20.0, "reasoning": "test"},
        ],
        "total_estimated_cost": 119.0,
        "budget_status": "within budget",
        "summary": "Estimated LKR 119.00 for 2 days in Kandy.",
    }

    audit = audit_itinerary(
        research_output=research_output,
        budget_output=budget_output,
        days=2,
        interests=["culture", "nature"],
        budget_limit=30000.0,
    )
    assert audit.completeness_score == 1.0, f"Expected perfect score, got {audit.completeness_score}"
    assert audit.budget_aligned is True
    assert audit.has_enough_attractions is True
    assert audit.interest_coverage == 1.0
    assert audit.warnings == []

    # --- Audit catches issues ---
    bad_audit = audit_itinerary(
        research_output={"destination_summary": "", "attractions": [], "budget_status": "x"},
        budget_output={"budget_status": "over budget", "total_estimated_cost": 999.0, "summary": "x"},
        days=3,
    )
    assert bad_audit.completeness_score < 1.0
    assert bad_audit.budget_aligned is False
    assert len(bad_audit.warnings) >= 2

    # --- Formatter builds valid itinerary ---
    itinerary = format_final_itinerary(
        destination="Kandy",
        days=2,
        user_goal="Cultural trip to Kandy.",
        attractions=research_output["attractions"],
        budget_output=budget_output,
        budget_summary=budget_output["summary"],
        warnings=[],
        suggestions=["Consider visiting the Botanical Garden."],
    )
    assert "Kandy 2-Day Travel Plan" in itinerary
    assert "Day 1" in itinerary
    assert "Day 2" in itinerary
    assert "Budget Summary" in itinerary
    assert "Budget Breakdown" in itinerary
    assert "Suggestions:" in itinerary

    # --- Validator confirms structure ---
    validation = validate_itinerary_text(itinerary, days=2)
    assert validation.is_valid is True
    assert validation.day_marker_count == 2

    # --- ReviewerOutput model contract ---
    output = ReviewerOutput(
        approved=True,
        approval_reason="Itinerary is complete and within budget.",
        warnings=[],
        suggestions=["Consider visiting the Botanical Garden."],
        completeness_score=1.0,
        budget_aligned=True,
        final_itinerary=itinerary,
    )
    dumped = output.model_dump()
    assert set(dumped.keys()) == {
        "approved",
        "approval_reason",
        "warnings",
        "suggestions",
        "completeness_score",
        "budget_aligned",
        "final_itinerary",
    }

    print("Reviewer evaluation passed.")


if __name__ == "__main__":
    evaluate_reviewer_pipeline()
