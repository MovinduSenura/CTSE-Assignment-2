"""Planner Agent implementation."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from Member_1_Planner.validation_tool import PlannerTaskContext, create_trip_tasks, validate_and_structure_trip_request


class PlannerOutput(BaseModel):
    normalized_destination: str
    trip_style: str
    user_goal: str
    budget_tier: Literal["low", "medium", "high"]
    daily_trip_pacing: Literal["relaxed", "balanced", "packed"]
    task_list: list[str] = Field(min_length=3)
    research_focus: list[str] = Field(min_length=1)
    required_budget_checks: list[str] = Field(min_length=4)
    planning_constraints: list[str] = Field(min_length=1)
    risk_flags: list[str]
    fallback_notes: list[str] = Field(min_length=1)
    planning_notes: list[str] = Field(min_length=1)


def run_planner_agent(state: dict, llm, logger: logging.Logger) -> dict:
    """Coordinate the trip request into a strict execution brief."""
    validation_output = validate_and_structure_trip_request(
        destination=state["destination"],
        budget=state["budget"],
        days=state["days"],
        interests=state["interests"],
    )
    task_context = PlannerTaskContext(
        normalized_destination=validation_output.normalized_destination,
        normalized_interests=validation_output.normalized_interests,
        days=state["days"],
        budget_tier=validation_output.budget_tier,
        daily_trip_pacing=validation_output.daily_trip_pacing,
        warnings=validation_output.warnings,
    )
    task_list = create_trip_tasks(task_context)
    prompt = _build_planner_prompt(state, validation_output.model_dump(), task_list)
    try:
        raw_result = llm.with_structured_output(PlannerOutput).invoke(prompt)
        result = _sanitize_planner_output(raw_result, validation_output, task_list, state)
    except Exception as exc:
        logger.warning("PLANNER_LLM_FALLBACK | %s", exc)
        result = _build_fallback_output(validation_output, task_list, state)
    logger.info("PLANNER_INPUT | %s", json.dumps(state, ensure_ascii=False, default=str))
    logger.info("PLANNER_VALIDATION | %s", validation_output.model_dump_json())
    logger.info("PLANNER_TASKS | %s", json.dumps(task_list, ensure_ascii=False))
    logger.info("PLANNER_OUTPUT | %s", result.model_dump_json())
    return {"planner_output": result.model_dump()}


def _build_planner_prompt(state: dict, tool_output: dict, task_list: list[str]) -> str:
    """Build the planner prompt with strict coordinator rules."""
    return f"""
You are the Planner Agent in a local travel-planning multi-agent system.
Your role is to coordinate work for the Researcher, Executor, and Reviewer.
Do not invent attractions, hotel names, transport options, or ticket prices.
Do not perform research, cost estimation, or final review yourself.
Convert the validated request into a machine-readable coordinator brief only.
Use only values present in the validated tool output and suggested task list.
If uncertain, copy validated values exactly instead of improvising.

Raw request:
Destination: {state['destination']}
Budget: {state['currency']} {state['budget']}
Days: {state['days']}
Interests: {", ".join(state['interests'])}

Validated tool output:
{tool_output}

Suggested task list from planner tool:
{task_list}

Return:
- normalized_destination
- trip_style
- user_goal
- budget_tier
- daily_trip_pacing
- task_list
- research_focus
- required_budget_checks
- planning_constraints
- risk_flags
- fallback_notes
- planning_notes

Rules:
- task_list must include explicit tasks for Researcher, Executor, and Reviewer
- use the suggested task list as the baseline and improve wording only if needed
- research_focus must use only normalized interests from the validation tool
- required_budget_checks must include accommodation, food, transport, and attractions
- risk_flags must reflect real planning risks from the validation tool warnings
- fallback_notes must explain how downstream agents should handle risky requests
- planning_constraints must preserve realism and prevent hallucinated planning
- never mention specific attraction names, exact ticket prices, or hotel names
"""


def _build_fallback_output(validation_output, task_list: list[str], state: dict) -> PlannerOutput:
    """Build a deterministic fallback planner output when LLM generation fails."""
    return PlannerOutput(
        normalized_destination=validation_output.normalized_destination,
        trip_style="Balanced trip",
        user_goal=f"Plan a realistic {state['days']}-day trip to {validation_output.normalized_destination}.",
        budget_tier=validation_output.budget_tier,
        daily_trip_pacing=validation_output.daily_trip_pacing,
        task_list=task_list,
        research_focus=validation_output.normalized_interests,
        required_budget_checks=["accommodation", "food", "transport", "attractions"],
        planning_constraints=validation_output.planning_constraints,
        risk_flags=validation_output.warnings,
        fallback_notes=["Use conservative planning assumptions if downstream data is incomplete."],
        planning_notes=["Keep outputs realistic and aligned with budget."],
    )


def _sanitize_planner_output(
    output: PlannerOutput,
    validation_output,
    task_list: list[str],
    state: dict,
) -> PlannerOutput:
    """Clamp planner output to validated values to reduce hallucinations."""
    allowed_interests = validation_output.normalized_interests
    sanitized_focus = [interest for interest in output.research_focus if interest in allowed_interests]
    if not sanitized_focus:
        sanitized_focus = allowed_interests

    sanitized_tasks = [task for task in output.task_list if any(role in task for role in ("Researcher", "Executor", "Reviewer"))]
    if len(sanitized_tasks) < 3:
        sanitized_tasks = task_list

    return PlannerOutput(
        normalized_destination=validation_output.normalized_destination,
        trip_style=output.trip_style or "Balanced trip",
        user_goal=output.user_goal or f"Plan a realistic {state['days']}-day trip to {validation_output.normalized_destination}.",
        budget_tier=validation_output.budget_tier,
        daily_trip_pacing=validation_output.daily_trip_pacing,
        task_list=sanitized_tasks,
        research_focus=sanitized_focus,
        required_budget_checks=["accommodation", "food", "transport", "attractions"],
        planning_constraints=validation_output.planning_constraints,
        risk_flags=validation_output.warnings,
        fallback_notes=output.fallback_notes or ["Use conservative planning assumptions if downstream data is incomplete."],
        planning_notes=output.planning_notes or ["Keep outputs realistic and aligned with budget."],
    )
