from Member_1_Planner.validation_tool import validate_and_structure_trip_request


def test_planner_validation_normalizes_and_deduplicates_interests() -> None:
    result = validate_and_structure_trip_request(
        destination=" Tokyo ",
        budget=900.0,
        days=3,
        interests=["Food", "anime", "food", " culture "],
    )
    assert result["normalized_destination"] == "Tokyo"
    assert result["normalized_interests"] == ["food", "anime", "culture"]
    assert result["budget_tier"] == "high"
    assert result["daily_trip_pacing"] == "balanced"


def test_planner_validation_rejects_invalid_budget() -> None:
    try:
        validate_and_structure_trip_request("Colombo", 0.0, 2, ["culture"])
    except ValueError as exc:
        assert "Budget" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid budget.")
