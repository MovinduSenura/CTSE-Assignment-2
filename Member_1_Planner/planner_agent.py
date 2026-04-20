"""Planner Agent implementation."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from Member_1_Planner.validation_tool import validate_and_structure_trip_request


class PlannerOutput(BaseModel):
    normalized_destination: str
    trip_style: str
    user_goal: str
    budget_tier: str
    daily_trip_pacing: str
    task_list: list[str]
    research_focus: list[str]
    required_budget_checks: list[str]
    planning_constraints: list[str]
    risk_flags: list[str]
    fallback_notes: list[str]
    planning_notes: list[str]


def run_planner_agent(state: dict, llm, logger: logging.Logger) -> dict:
    """Coordinate the trip request into a strict execution brief."""
    tool_output = validate_and_structure_trip_request(
        destination=state["destination"],
        budget=state["budget"],
        days=state["days"],
        interests=state["interests"],
    )
    prompt = f"""
You are the Planner Agent in a local travel-planning multi-agent system.
Your role is to coordinate work for the Research Agent, Executor Agent, and Reviewer Agent.
Do not invent attractions, hotel names, transport options, or ticket prices.
Convert the validated request into a machine-readable plan only.

Raw request:
Destination: {state['destination']}
Budget: {state['currency']} {state['budget']}
Days: {state['days']}
Interests: {", ".join(state['interests'])}

Validated tool output:
{tool_output}

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
- required_budget_checks must include accommodation, food, transport, and attractions
"""
    result = llm.with_structured_output(PlannerOutput).invoke(prompt)
    logger.info("PLANNER | input=%s | tool=%s | output=%s", state, tool_output, result.model_dump())
    return {"planner_output": result.model_dump()}
