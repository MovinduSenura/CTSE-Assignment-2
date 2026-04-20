from Member_4_Reviewer.formatter_tool import audit_itinerary, format_final_itinerary


def test_reviewer_tool_flags_over_budget() -> None:
    research_output = {
        "destination_summary": "Short city break.",
        "attractions": [
            {
                "name": "Museum",
                "description": "A museum.",
                "estimated_time_hours": 2.0,
                "interest_match": "culture",
                "source": "example",
            }
        ],
    }
    budget_output = {
        "currency": "USD",
        "line_items": [{"category": "Accommodation", "amount": 100.0, "reasoning": "test"}],
        "total_estimated_cost": 1000.0,
        "budget_status": "over budget",
        "summary": "Over budget.",
    }
    warnings = audit_itinerary(research_output, budget_output, days=3)
    assert any("above the user's budget" in item for item in warnings)


def test_formatter_tool_builds_final_itinerary() -> None:
    itinerary = format_final_itinerary(
        destination="Tokyo",
        days=2,
        user_goal="Short city break.",
        attractions=[
            {
                "name": "Senso-ji",
                "description": "Historic temple.",
                "estimated_time_hours": 2.0,
                "interest_match": "culture",
                "source": "https://example.com",
            }
        ],
        budget_summary="Estimated USD 300.00 total.",
        warnings=[],
    )
    assert "Tokyo 2-Day Travel Plan" in itinerary
    assert "Budget Summary" in itinerary
