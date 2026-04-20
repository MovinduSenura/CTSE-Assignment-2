"""Standalone evaluation harness for the Planner member's contribution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Member_1_Planner.planner_agent import PlannerOutput
from Member_1_Planner.validation_tool import PlannerTaskContext, create_trip_tasks, parse_trip_request, validate_and_structure_trip_request


def evaluate_planner_pipeline() -> None:
    """Run deterministic checks for planner parsing, validation, and task creation."""
    request = parse_trip_request("Plan a 2-day trip to Kandy under 30000 for culture and food")
    validation = validate_and_structure_trip_request(
        destination=request.destination,
        budget=request.budget,
        days=request.days,
        interests=request.interests,
    )
    tasks = create_trip_tasks(
        PlannerTaskContext(
            normalized_destination=validation.normalized_destination,
            normalized_interests=validation.normalized_interests,
            days=request.days,
            budget_tier=validation.budget_tier,
            daily_trip_pacing=validation.daily_trip_pacing,
            warnings=validation.warnings,
        )
    )

    assert request.destination == "Kandy"
    assert request.days == 2
    assert request.budget == 30000.0
    assert request.interests == ["culture", "food"]
    assert validation.normalized_destination == "Kandy"
    assert validation.normalized_interests == ["culture", "food"]
    assert len(tasks) >= 3
    assert any(task.startswith("Researcher:") for task in tasks)
    assert any(task.startswith("Executor:") for task in tasks)
    assert any(task.startswith("Reviewer:") for task in tasks)

    planner_output = PlannerOutput(
        normalized_destination=validation.normalized_destination,
        trip_style="Balanced cultural short trip",
        user_goal="Create a realistic 2-day trip to Kandy focused on culture and food.",
        budget_tier=validation.budget_tier,
        daily_trip_pacing=validation.daily_trip_pacing,
        task_list=tasks,
        research_focus=validation.normalized_interests,
        required_budget_checks=["accommodation", "food", "transport", "attractions"],
        planning_constraints=validation.planning_constraints,
        risk_flags=validation.warnings,
        fallback_notes=["Reduce paid activities if the Executor estimates costs above the budget."],
        planning_notes=["Keep each day realistic and aligned with the user budget."],
    )

    assert planner_output.research_focus == ["culture", "food"]
    assert set(planner_output.required_budget_checks) == {"accommodation", "food", "transport", "attractions"}
    print("Planner evaluation passed.")


if __name__ == "__main__":
    evaluate_planner_pipeline()
