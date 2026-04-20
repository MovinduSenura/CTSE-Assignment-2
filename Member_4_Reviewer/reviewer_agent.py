"""Reviewer Agent implementation."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from Member_4_Reviewer.formatter_tool import audit_itinerary, format_final_itinerary


class ReviewerOutput(BaseModel):
    approved: bool
    warnings: list[str]
    final_itinerary: str


def run_reviewer_agent(state: dict, llm, logger: logging.Logger) -> dict:
    """Review the itinerary for completeness and realism."""
    warnings = audit_itinerary(
        research_output=state["research_output"],
        budget_output=state["budget_output"],
        days=state["days"],
    )
    prompt = f"""
You are the Reviewer Agent.
Check whether the itinerary is complete, realistic, and budget-aware.

Planner output:
{state['planner_output']}

Research output:
{state['research_output']}

Budget output:
{state['budget_output']}

Warnings from tool:
{warnings}

Return:
- approved
- warnings
- final_itinerary
"""
    result = llm.with_structured_output(ReviewerOutput).invoke(prompt)
    result_data = result.model_dump()
    if len(result_data["final_itinerary"].strip()) < 120:
        result_data["final_itinerary"] = format_final_itinerary(
            destination=state["destination"],
            days=state["days"],
            user_goal=state["planner_output"]["user_goal"],
            attractions=state["research_output"]["attractions"],
            budget_summary=state["budget_output"]["summary"],
            warnings=result_data["warnings"] or warnings,
        )
    logger.info("REVIEWER | input=%s | warnings=%s | output=%s", state, warnings, result_data)
    return {"reviewer_output": result_data}
