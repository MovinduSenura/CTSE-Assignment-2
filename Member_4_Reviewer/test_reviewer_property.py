"""Property-based tests for the Reviewer Agent formatter tool."""

from hypothesis import given, strategies as st

from Member_4_Reviewer.formatter_tool import (
    AuditResult,
    audit_itinerary,
    format_final_itinerary,
    validate_itinerary_text,
)


def _make_attraction(name: str = "Temple", interest: str = "culture") -> dict:
    return {
        "name": name,
        "description": "A notable attraction.",
        "estimated_time_hours": 2.0,
        "interest_match": interest,
        "source": "https://example.com",
    }


def _make_budget_output() -> dict:
    return {
        "currency": "USD",
        "line_items": [
            {"category": "Accommodation", "amount": 100.0, "reasoning": "test"},
        ],
        "total_estimated_cost": 100.0,
        "budget_status": "within budget",
        "summary": "Estimated USD 100.00 total.",
    }


@given(
    days=st.integers(min_value=1, max_value=14),
    num_attractions=st.integers(min_value=1, max_value=10),
    budget_status=st.sampled_from(["within budget", "over budget"]),
    summary=st.text(min_size=0, max_size=60),
)
def test_audit_always_returns_valid_result(
    days: int,
    num_attractions: int,
    budget_status: str,
    summary: str,
) -> None:
    attractions = [_make_attraction(name=f"Place {i}") for i in range(num_attractions)]
    research_output = {
        "destination_summary": summary,
        "attractions": attractions,
    }
    budget_output = {
        "currency": "USD",
        "line_items": [],
        "total_estimated_cost": 100.0,
        "budget_status": budget_status,
        "summary": "test",
    }
    result = audit_itinerary(research_output, budget_output, days)
    assert isinstance(result, AuditResult)
    assert 0.0 <= result.completeness_score <= 1.0
    assert 0.0 <= result.interest_coverage <= 1.0
    assert isinstance(result.warnings, list)
    assert isinstance(result.suggestions, list)


@given(
    days=st.integers(min_value=1, max_value=14),
    interests=st.lists(
        st.sampled_from(["culture", "food", "nature", "history", "shopping"]),
        min_size=1,
        max_size=5,
    ),
)
def test_audit_interest_coverage_bounded(days: int, interests: list[str]) -> None:
    attractions = [_make_attraction(interest="culture")]
    research_output = {"destination_summary": "ok", "attractions": attractions}
    budget_output = {
        "currency": "USD",
        "line_items": [],
        "total_estimated_cost": 100.0,
        "budget_status": "within budget",
        "summary": "test",
    }
    result = audit_itinerary(
        research_output, budget_output, days, interests=interests
    )
    assert 0.0 <= result.interest_coverage <= 1.0


@given(
    destination=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=1,
        max_size=20,
    ).map(str.strip).filter(bool),
    days=st.integers(min_value=1, max_value=7),
)
def test_formatter_always_contains_destination_and_day1(
    destination: str,
    days: int,
) -> None:
    itinerary = format_final_itinerary(
        destination=destination,
        days=days,
        user_goal="A trip.",
        attractions=[_make_attraction()],
        budget_output=_make_budget_output(),
        budget_summary="Estimated 100.",
        warnings=[],
    )
    assert destination in itinerary
    assert "Day 1" in itinerary
    assert "Budget Summary" in itinerary


@given(text=st.text(min_size=0, max_size=500))
def test_validate_itinerary_never_crashes(text: str) -> None:
    result = validate_itinerary_text(text, days=1)
    assert isinstance(result.is_valid, bool)
    assert isinstance(result.issues, list)
    assert result.day_marker_count >= 0
