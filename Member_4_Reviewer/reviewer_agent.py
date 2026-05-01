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

Rules:
- final_itinerary must include a short overview
- final_itinerary must include a day-by-day plan using labels like 'Day 1', 'Day 2'
- final_itinerary must include a budget summary
- final_itinerary should include a budget breakdown by category when available
- do not return only a generic approval paragraph
"""
    try:
        result = llm.with_structured_output(ReviewerOutput).invoke(prompt)
        result_data = result.model_dump()
    except Exception as exc:
        # Fallback: build a deterministic final itinerary
        logger.warning("REVIEWER_LLM_FALLBACK | %s", exc)
        final_itinerary = format_final_itinerary(
            destination=state["destination"],
            days=state["days"],
            user_goal=state["planner_output"]["user_goal"],
            attractions=state["research_output"]["attractions"],
            budget_output=state["budget_output"],
            budget_summary=state["budget_output"]["summary"],
            warnings=warnings,
        )
        result_data = {"approved": True, "warnings": warnings, "final_itinerary": final_itinerary}

    if not _looks_like_real_itinerary(result_data["final_itinerary"], state["days"]):
        result_data["final_itinerary"] = format_final_itinerary(
            destination=state["destination"],
            days=state["days"],
            user_goal=state["planner_output"]["user_goal"],
            attractions=state["research_output"]["attractions"],
            budget_output=state["budget_output"],
            budget_summary=state["budget_output"]["summary"],
            warnings=result_data.get("warnings") or warnings,
        )
    logger.info("REVIEWER | input=%s | warnings=%s | output=%s", state, warnings, result_data)
    return {"reviewer_output": result_data}


def _looks_like_real_itinerary(final_itinerary: str, days: int) -> bool:
    """Check whether the reviewer output contains a genuine day-by-day itinerary."""
    text = final_itinerary.strip()
    if len(text) < 120:
        return False
    if "Budget Summary" not in text:
        return False
    day_markers = sum(1 for day in range(1, days + 1) if f"Day {day}" in text)
    return day_markers >= min(days, 2)
