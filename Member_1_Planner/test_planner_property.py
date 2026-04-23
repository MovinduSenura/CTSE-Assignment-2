from hypothesis import given, strategies as st

import Member_1_Planner.validation_tool as planner_validation_tool
from Member_1_Planner.validation_tool import PlannerTaskContext, create_trip_tasks, validate_and_structure_trip_request
from Member_2_Researcher.attraction_tool import DestinationContext


def _allow_sri_lanka_destination(destination: str, timeout: int = 10) -> DestinationContext:
    return DestinationContext(
        destination=destination.strip(),
        display_name=f"{destination.strip()}, Sri Lanka",
        latitude=7.2906,
        longitude=80.6337,
        country="Sri Lanka",
    )


@given(
    destination=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Zs")),
        min_size=1,
        max_size=20,
    )
    .map(str.strip)
    .filter(bool)
    .filter(lambda destination: destination.lower() not in planner_validation_tool.KNOWN_NON_SRI_LANKAN_DESTINATIONS),
    budget=st.floats(min_value=1, max_value=100000, allow_nan=False, allow_infinity=False),
    days=st.integers(min_value=1, max_value=14),
    interests=st.lists(
        st.sampled_from(["culture", "food", "anime", "history", "nature", "shopping"]),
        min_size=0,
        max_size=8,
    ),
)
def test_validation_properties(destination: str, budget: float, days: int, interests: list[str]) -> None:
    original_resolve_destination = planner_validation_tool.resolve_destination
    planner_validation_tool.resolve_destination = _allow_sri_lanka_destination
    try:
        result = validate_and_structure_trip_request(
            destination=destination,
            budget=budget,
            days=days,
            interests=interests,
        )
    finally:
        planner_validation_tool.resolve_destination = original_resolve_destination
    assert result.normalized_destination
    assert result.budget_tier in {"low", "medium", "high"}
    assert result.daily_trip_pacing in {"relaxed", "balanced", "packed"}
    assert len(result.normalized_interests) >= 1
    assert len(result.normalized_interests) == len(set(result.normalized_interests))


@given(
    days=st.integers(min_value=1, max_value=14),
    budget_tier=st.sampled_from(["low", "medium", "high"]),
    pacing=st.sampled_from(["relaxed", "balanced", "packed"]),
    warnings=st.lists(st.text(min_size=1, max_size=60), min_size=0, max_size=3),
)
def test_task_generation_properties(
    days: int,
    budget_tier: str,
    pacing: str,
    warnings: list[str],
) -> None:
    tasks = create_trip_tasks(
        PlannerTaskContext(
            normalized_destination="Kandy",
            normalized_interests=["culture", "food"],
            days=days,
            budget_tier=budget_tier,  # type: ignore[arg-type]
            daily_trip_pacing=pacing,  # type: ignore[arg-type]
            warnings=warnings,
        )
    )
    assert len(tasks) >= 3
    assert any(task.startswith("Researcher:") for task in tasks)
    assert any(task.startswith("Executor:") for task in tasks)
    assert any(task.startswith("Reviewer:") for task in tasks)
