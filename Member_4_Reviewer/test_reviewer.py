"""Unit tests for the Reviewer Agent formatter tool and output models."""

import pytest

from Member_4_Reviewer.formatter_tool import (
    AuditResult,
    ItineraryValidationResult,
    audit_itinerary,
    format_final_itinerary,
    validate_itinerary_text,
)
from Member_4_Reviewer.reviewer_agent import ReviewerOutput


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

def _make_attraction(
    name: str = "Museum",
    interest: str = "culture",
    source: str = "https://example.com",
) -> dict:
    return {
        "name": name,
        "description": "A notable attraction.",
        "estimated_time_hours": 2.0,
        "interest_match": interest,
        "source": source,
    }


def _make_research_output(
    attractions: list[dict] | None = None,
    summary: str = "Short city break.",
) -> dict:
    return {
        "destination_summary": summary,
        "attractions": attractions or [_make_attraction()],
    }


def _make_budget_output(
    status: str = "within budget",
    total: float = 150.0,
) -> dict:
    return {
        "currency": "USD",
        "line_items": [
            {"category": "Accommodation", "amount": 100.0, "reasoning": "test"},
        ],
        "total_estimated_cost": total,
        "budget_status": status,
        "summary": f"Estimated USD {total:.2f} total.",
    }


# ---------------------------------------------------------------------------
# audit_itinerary tests
# ---------------------------------------------------------------------------

def test_audit_flags_over_budget() -> None:
    result = audit_itinerary(
        research_output=_make_research_output(),
        budget_output=_make_budget_output(status="over budget"),
        days=1,
    )
    assert any("above the user's budget" in w for w in result.warnings)
    assert result.budget_aligned is False


def test_audit_flags_not_enough_attractions() -> None:
    result = audit_itinerary(
        research_output=_make_research_output(attractions=[_make_attraction()]),
        budget_output=_make_budget_output(),
        days=3,
    )
    assert any("Not enough attractions" in w for w in result.warnings)
    assert result.has_enough_attractions is False


def test_audit_flags_missing_destination_summary() -> None:
    result = audit_itinerary(
        research_output=_make_research_output(summary=""),
        budget_output=_make_budget_output(),
        days=1,
    )
    assert any("Destination summary is missing" in w for w in result.warnings)


def test_audit_flags_low_interest_coverage() -> None:
    attractions = [_make_attraction(interest="food")]
    result = audit_itinerary(
        research_output=_make_research_output(attractions=attractions),
        budget_output=_make_budget_output(),
        days=1,
        interests=["culture", "food", "nature", "history"],
    )
    assert result.interest_coverage == 0.25
    assert any("interests are covered" in w for w in result.warnings)


def test_audit_flags_overpacked_itinerary() -> None:
    attractions = [_make_attraction(name=f"Place {i}") for i in range(10)]
    result = audit_itinerary(
        research_output=_make_research_output(attractions=attractions),
        budget_output=_make_budget_output(),
        days=2,
    )
    assert any("overpacked" in w for w in result.warnings)
    assert any("limiting attractions" in s for s in result.suggestions)


def test_audit_flags_missing_source_urls() -> None:
    attractions = [_make_attraction(source="")]
    result = audit_itinerary(
        research_output=_make_research_output(attractions=attractions),
        budget_output=_make_budget_output(),
        days=1,
    )
    assert any("missing source" in s for s in result.suggestions)


def test_audit_completeness_score_is_perfect_for_clean_input() -> None:
    result = audit_itinerary(
        research_output=_make_research_output(),
        budget_output=_make_budget_output(),
        days=1,
        interests=["culture"],
    )
    assert result.completeness_score == 1.0
    assert result.warnings == []


def test_audit_completeness_score_decreases_with_issues() -> None:
    result = audit_itinerary(
        research_output=_make_research_output(summary=""),
        budget_output=_make_budget_output(status="over budget"),
        days=3,
    )
    assert result.completeness_score < 1.0
    assert len(result.warnings) >= 2


def test_audit_rejects_invalid_days() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        audit_itinerary(
            research_output=_make_research_output(),
            budget_output=_make_budget_output(),
            days=0,
        )


def test_audit_rejects_missing_attractions_key() -> None:
    with pytest.raises(ValueError, match="attractions"):
        audit_itinerary(
            research_output={"destination_summary": "ok"},
            budget_output=_make_budget_output(),
            days=1,
        )


def test_audit_budget_utilization_low_suggestion() -> None:
    result = audit_itinerary(
        research_output=_make_research_output(),
        budget_output=_make_budget_output(total=10.0),
        days=1,
        budget_limit=10000.0,
    )
    assert any("utilization is very low" in s for s in result.suggestions)


# ---------------------------------------------------------------------------
# validate_itinerary_text tests
# ---------------------------------------------------------------------------

def test_validation_passes_for_valid_itinerary() -> None:
    text = (
        "Kandy 2-Day Travel Plan\n\n"
        "Overview: A cultural trip.\n\n"
        "Day 1: Visit Temple.\n"
        "Day 2: Visit Garden.\n\n"
        "Budget Summary: Estimated USD 150.00 total.\n"
        "Recommended attractions:\n- Temple (https://example.com)"
    )
    result = validate_itinerary_text(text, days=2)
    assert result.is_valid is True
    assert result.has_overview is True
    assert result.has_day_markers is True
    assert result.has_budget_summary is True
    assert result.day_marker_count == 2


def test_validation_fails_for_missing_day_markers() -> None:
    text = (
        "Kandy Travel Plan\n\nOverview: A trip.\n\n"
        "Budget Summary: Estimated USD 100.\n"
        "Some extra padding text to reach the minimum length threshold."
    )
    result = validate_itinerary_text(text, days=2)
    assert result.has_day_markers is False
    assert result.is_valid is False


def test_validation_fails_for_missing_budget_summary() -> None:
    text = (
        "Kandy Travel Plan\n\nOverview: A trip.\n\n"
        "Day 1: Visit Temple.\n"
        "Some extra padding text to reach the minimum length threshold."
    )
    result = validate_itinerary_text(text, days=1)
    assert result.has_budget_summary is False
    assert result.is_valid is False


def test_validation_fails_for_too_short_text() -> None:
    result = validate_itinerary_text("Short.", days=1)
    assert result.is_valid is False
    assert any("too short" in issue for issue in result.issues)


def test_validation_rejects_invalid_days() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        validate_itinerary_text("Some text", days=0)


# ---------------------------------------------------------------------------
# format_final_itinerary tests
# ---------------------------------------------------------------------------

def test_formatter_builds_itinerary_with_structure() -> None:
    itinerary = format_final_itinerary(
        destination="Kandy",
        days=2,
        user_goal="Short city break.",
        attractions=[_make_attraction()],
        budget_output=_make_budget_output(),
        budget_summary="Estimated USD 150.00 total.",
        warnings=[],
    )
    assert "Kandy 2-Day Travel Plan" in itinerary
    assert "Overview:" in itinerary
    assert "Day 1" in itinerary
    assert "Day 2" in itinerary
    assert "Budget Summary" in itinerary
    assert "Budget Breakdown" in itinerary
    assert "Accommodation" in itinerary


def test_formatter_includes_warnings_when_present() -> None:
    itinerary = format_final_itinerary(
        destination="Ella",
        days=1,
        user_goal="Nature trip.",
        attractions=[_make_attraction()],
        budget_output=_make_budget_output(),
        budget_summary="Estimated USD 80.00 total.",
        warnings=["Over budget."],
    )
    assert "Warnings:" in itinerary
    assert "Over budget." in itinerary


def test_formatter_includes_suggestions_when_provided() -> None:
    itinerary = format_final_itinerary(
        destination="Galle",
        days=1,
        user_goal="Beach trip.",
        attractions=[_make_attraction()],
        budget_output=_make_budget_output(),
        budget_summary="Estimated USD 60.00 total.",
        warnings=[],
        suggestions=["Add more free activities."],
    )
    assert "Suggestions:" in itinerary
    assert "Add more free activities." in itinerary


def test_formatter_wraps_attractions_for_multiday() -> None:
    itinerary = format_final_itinerary(
        destination="Kandy",
        days=3,
        user_goal="Explore Kandy.",
        attractions=[_make_attraction()],
        budget_output=_make_budget_output(),
        budget_summary="Estimated USD 200.00 total.",
        warnings=[],
    )
    assert "Day 1" in itinerary
    assert "Day 2" in itinerary
    assert "Day 3" in itinerary


def test_formatter_rejects_empty_destination() -> None:
    with pytest.raises(ValueError, match="Destination"):
        format_final_itinerary(
            destination="",
            days=1,
            user_goal="Trip.",
            attractions=[_make_attraction()],
            budget_output=_make_budget_output(),
            budget_summary="ok",
            warnings=[],
        )


def test_formatter_rejects_empty_attractions() -> None:
    with pytest.raises(ValueError, match="attraction"):
        format_final_itinerary(
            destination="Kandy",
            days=1,
            user_goal="Trip.",
            attractions=[],
            budget_output=_make_budget_output(),
            budget_summary="ok",
            warnings=[],
        )


# ---------------------------------------------------------------------------
# ReviewerOutput model tests
# ---------------------------------------------------------------------------

def test_reviewer_output_model_holds_expected_values() -> None:
    output = ReviewerOutput(
        approved=True,
        approval_reason="Itinerary is complete.",
        warnings=[],
        suggestions=["Consider adding a food tour."],
        completeness_score=0.95,
        budget_aligned=True,
        final_itinerary="Full itinerary text here.",
    )
    assert output.approved is True
    assert output.completeness_score == 0.95
    assert output.budget_aligned is True


def test_reviewer_output_score_bounded() -> None:
    with pytest.raises(Exception):
        ReviewerOutput(
            approved=True,
            approval_reason="ok",
            warnings=[],
            completeness_score=1.5,
            budget_aligned=True,
            final_itinerary="text",
        )
