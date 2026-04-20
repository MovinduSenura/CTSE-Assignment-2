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


def run_executor_agent(state: dict, llm, logger: logging.Logger) -> dict:
    """Estimate travel costs from researched data."""
    tool_output = estimate_trip_budget(
        destination_context=state["destination_context"],
        days=state["days"],
        budget_limit=state["budget"],
        attraction_count=len(state["research_output"]["attractions"]),
        currency=state["currency"],
    )
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
"""
    result = llm.with_structured_output(ExecutorOutput).invoke(prompt)
    logger.info("EXECUTOR | input=%s | tool=%s | output=%s", state, tool_output, result.model_dump())
    return {"budget_output": result.model_dump()}
