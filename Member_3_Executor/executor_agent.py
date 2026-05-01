"""Executor Agent implementation."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from Member_3_Executor.budget_tool import estimate_trip_budget


class BudgetLineItem(BaseModel):
    category: str
    amount: float
    reasoning: str


class ExecutorOutput(BaseModel):
    currency: str
    line_items: list[BudgetLineItem]
    total_estimated_cost: float
    budget_status: str
    summary: str
    researcher_budget: float | None = None
    researcher_budget_status: str | None = None


def run_executor_agent(state: dict, llm, logger: logging.Logger) -> dict:
    """Estimate travel costs from researched data."""
    tool_output = estimate_trip_budget(
        destination_context=state["destination_context"],
        days=state["days"],
        budget_limit=state["budget"],
        attraction_count=len(state["research_output"]["attractions"]),
        currency=state["currency"],
    )
    _attach_researcher_budget_status(tool_output, state.get("research_output", {}))

    # If no LLM is available (offline mode), return deterministic tool output
    if llm is None:
        logger.info("EXECUTOR | running in offline mode, returning tool output")
        return {"budget_output": tool_output}

    prompt = f"""
You are the Executor Agent.
Rewrite the budget tool output into a clear execution and cost summary while preserving all numbers.

Budget tool output:
{tool_output}

Return:
- currency
- line_items
- total_estimated_cost
- budget_status
- summary
- researcher_budget (optional)
- researcher_budget_status (optional)
"""
    try:
        result = llm.with_structured_output(ExecutorOutput).invoke(prompt)
        payload = result.model_dump()
    except Exception as exc:
        logger.warning("EXECUTOR_LLM_FALLBACK | %s", exc)
        payload = tool_output

    logger.info("EXECUTOR | input=%s | tool=%s | output=%s", state, tool_output, payload)
    return {"budget_output": payload}


def _attach_researcher_budget_status(tool_output: dict, research_output: dict) -> None:
    """Attach comparison against researcher-suggested budget, when provided."""
    researcher_budget = research_output.get("suggested_budget")
    if researcher_budget is None:
        return

    total = float(tool_output.get("total_estimated_cost", 0.0))
    researcher_status = "within researcher budget" if total <= researcher_budget else "over researcher budget"
    tool_output["researcher_budget"] = researcher_budget
    tool_output["researcher_budget_status"] = researcher_status
