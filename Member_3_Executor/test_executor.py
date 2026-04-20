from Member_3_Executor.budget_tool import estimate_trip_budget


def test_executor_budget_tool_marks_trip_within_budget() -> None:
    context = {
        "destination": "Colombo",
        "display_name": "Colombo, Sri Lanka",
        "latitude": 6.9271,
        "longitude": 79.8612,
        "country": "Sri Lanka",
    }
    result = estimate_trip_budget(context, days=3, budget_limit=500.0, attraction_count=4)
    assert result["total_estimated_cost"] > 0
    assert result["budget_status"] == "within budget"
    assert len(result["line_items"]) == 4
