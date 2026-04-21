import Member_1_Planner.validation_tool as planner_validation_tool
from Member_1_Planner.planner_agent import PlannerOutput
from Member_1_Planner.validation_tool import (
    PlannerRequestInput,
    PlannerTaskContext,
    PlannerValidationResult,
    create_trip_tasks,
    parse_trip_request,
    validate_and_structure_trip_request,
)
from Member_2_Researcher.attraction_tool import DestinationContext


def _allow_sri_lanka_destination(destination: str, timeout: int = 10) -> DestinationContext:
    return DestinationContext(
        destination=destination.strip(),
        display_name=f"{destination.strip()}, Sri Lanka",
        latitude=7.2906,
        longitude=80.6337,
        country="Sri Lanka",
    )


def _reject_non_sri_lanka_destination(destination: str, timeout: int = 10) -> DestinationContext:
    raise ValueError(f"Destination '{destination.strip()}' is outside Sri Lanka.")


def test_parse_trip_request_from_natural_language() -> None:
    result: PlannerRequestInput = parse_trip_request(
        "Plan a 2-day trip to Kandy under 30000 for culture and food"
    )
    assert result.model_dump() == {
        "destination": "Kandy",
        "days": 2,
        "budget": 30000.0,
        "currency": "LKR",
        "interests": ["culture", "food"],
    }


def test_parse_trip_request_extracts_lkr_currency() -> None:
    result = parse_trip_request(
        "Plan a 2-day trip to Kandy under LKR 30000 for culture and food"
    )
    assert result.destination == "Kandy"
    assert result.days == 2
    assert result.budget == 30000.0
    assert result.currency == "LKR"
    assert result.interests == ["culture", "food"]


def test_parse_trip_request_extracts_rs_currency() -> None:
    result = parse_trip_request(
        "Plan a 1-day trip to Galle under Rs 10000 for beach and food"
    )
    assert result.currency == "LKR"


def test_planner_validation_normalizes_and_deduplicates_interests() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        result = validate_and_structure_trip_request(
            destination=" Kandy ",
            budget=900.0,
            days=3,
            interests=["Food", "heritage", "food", " culture "],
            currency="USD",
        )
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination

    assert result.normalized_destination == "Kandy"
    assert result.normalized_interests == ["food", "heritage", "culture"]
    assert result.budget_tier == "high"
    assert result.daily_trip_pacing == "balanced"


def test_planner_validation_rejects_invalid_budget() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        validate_and_structure_trip_request("Colombo", 0.0, 2, ["culture"])
    except ValueError as exc:
        assert "Budget" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid budget.")
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination


def test_parse_trip_request_rejects_missing_days() -> None:
    try:
        parse_trip_request("Plan a trip to Kandy under 30000 for culture and food")
    except ValueError as exc:
        assert "number of days" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing days.")


def test_full_planner_pipeline_handles_duplicate_interests() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        request = parse_trip_request(
            "Plan a 3-day trip to Kandy under 900 for food and culture and food"
        )
        result = validate_and_structure_trip_request(
            destination=request.destination,
            budget=request.budget,
            days=request.days,
            interests=request.interests,
        )
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination

    assert result.normalized_interests == ["food", "culture"]


def test_create_trip_tasks_returns_downstream_assignments() -> None:
    tasks = create_trip_tasks(
        PlannerTaskContext(
            normalized_destination="Kandy",
            normalized_interests=["culture", "food"],
            days=2,
            budget_tier="medium",
            daily_trip_pacing="balanced",
            warnings=[],
        )
    )
    assert any("Researcher:" in task for task in tasks)
    assert any("Executor:" in task for task in tasks)
    assert any("Reviewer:" in task for task in tasks)
    assert any("Kandy" in task for task in tasks)


def test_create_trip_tasks_adds_risk_handling_when_warnings_exist() -> None:
    tasks = create_trip_tasks(
        PlannerTaskContext(
            normalized_destination="Tokyo",
            normalized_interests=["culture", "food", "anime"],
            days=3,
            budget_tier="low",
            daily_trip_pacing="packed",
            warnings=["The itinerary may become rushed unless activities are limited per day."],
        )
    )
    assert any("low-cost" in task for task in tasks)
    assert any("risks flagged" in task for task in tasks)


def test_planner_validation_rejects_empty_destination() -> None:
    try:
        validate_and_structure_trip_request("   ", 500.0, 2, ["culture"])
    except ValueError as exc:
        assert "Destination" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty destination.")


def test_planner_validation_rejects_too_many_days() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        validate_and_structure_trip_request("Kandy", 5000.0, 20, ["culture"])
    except ValueError as exc:
        assert "14 or fewer" in str(exc)
    else:
        raise AssertionError("Expected ValueError for too many days.")
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination


def test_planner_validation_flags_expensive_city_and_packed_request() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        result = validate_and_structure_trip_request(
            destination="Kandy",
            budget=240.0,
            days=3,
            interests=["culture", "food", "nature", "shopping", "history", "spirituality", "photography"],
            currency="USD",
        )
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination

    assert result.budget_tier == "medium"
    assert result.daily_trip_pacing == "packed"
    assert any("prioritization" in item.lower() for item in result.warnings)
    assert any("rushed" in item.lower() for item in result.warnings)


def test_planner_validation_result_shape_is_report_ready() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        result: PlannerValidationResult = validate_and_structure_trip_request(
            destination="Colombo",
            budget=300.0,
            days=2,
            interests=["food"],
            currency="USD",
        )
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination

    assert set(result.model_dump().keys()) == {
        "normalized_destination",
        "currency",
        "normalized_interests",
        "budget_tier",
        "daily_trip_pacing",
        "warnings",
        "planning_constraints",
    }


def test_planner_output_contract_requires_downstream_coordination_fields() -> None:
    output = PlannerOutput(
        normalized_destination="Tokyo",
        trip_style="Balanced city break",
        user_goal="Create a realistic short trip focused on culture and food.",
        budget_tier="medium",
        daily_trip_pacing="balanced",
        task_list=[
            "Researcher: identify attractions that match culture and food interests.",
            "Executor: estimate accommodation, food, transport, and attraction costs.",
            "Reviewer: verify completeness, realism, and budget fit.",
        ],
        research_focus=["culture", "food"],
        required_budget_checks=["accommodation", "food", "transport", "attractions"],
        planning_constraints=["Plan for exactly 3 travel day(s)."],
        risk_flags=["Short trip requires prioritization."],
        fallback_notes=["Reduce paid attractions if the Executor finds the trip over budget."],
        planning_notes=["Keep the schedule realistic and avoid overpacking each day."],
    )
    assert any("Researcher" in task for task in output.task_list)
    assert any("Executor" in task for task in output.task_list)
    assert any("Reviewer" in task for task in output.task_list)


def test_planner_validation_result_uses_strict_model_dump() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        result = validate_and_structure_trip_request(
            destination="Kandy",
            budget=12000.0,
            days=2,
            interests=["culture", "food"],
            currency="USD",
        )
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination

    dumped = result.model_dump()
    assert dumped["normalized_destination"] == "Kandy"
    assert dumped["budget_tier"] in {"low", "medium", "high"}


def test_planner_validation_uses_lkr_thresholds() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        low_result = validate_and_structure_trip_request(
            destination="Kandy",
            budget=9000.0,
            days=2,
            interests=["culture", "food"],
            currency="LKR",
        )
        medium_result = validate_and_structure_trip_request(
            destination="Kandy",
            budget=50000.0,
            days=2,
            interests=["culture", "food"],
            currency="LKR",
        )
        high_result = validate_and_structure_trip_request(
            destination="Kandy",
            budget=150000.0,
            days=2,
            interests=["culture", "food"],
            currency="LKR",
        )
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination

    assert low_result.budget_tier == "low"
    assert medium_result.budget_tier == "medium"
    assert high_result.budget_tier == "high"


def test_planner_validation_rejects_non_sri_lankan_destination() -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _reject_non_sri_lanka_destination
    try:
        validate_and_structure_trip_request(
            destination="Tokyo",
            budget=900.0,
            days=3,
            interests=["food", "anime"],
            currency="USD",
        )
    except ValueError as exc:
        assert "outside Sri Lanka" in str(exc)
    else:
        raise AssertionError("Expected ValueError for a destination outside Sri Lanka.")
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination
