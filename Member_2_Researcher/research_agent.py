"""Research Agent implementation."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from Member_2_Researcher.attraction_tool import resolve_destination, search_attractions


class AttractionRecommendation(BaseModel):
    name: str
    description: str
    estimated_time_hours: float
    interest_match: str
    source: str


class ResearchOutput(BaseModel):
    destination_summary: str
    attractions: list[AttractionRecommendation]


def run_research_agent(state: dict, llm, logger: logging.Logger) -> dict:
    """Research attractions using external tools and summarize them."""
    destination_context = resolve_destination(state["destination"])
    attractions = search_attractions(destination_context, state["interests"], limit=max(state["days"] * 2, 4))
    prompt = f"""
You are the Research Agent.
Use only the tool output below. Do not make up attractions.

Destination context:
{destination_context}

Attractions:
{attractions}

Return:
- destination_summary
- attractions
"""
    result = llm.with_structured_output(ResearchOutput).invoke(prompt)
    logger.info("RESEARCH | input=%s | destination=%s | attractions=%s | output=%s", state, destination_context, attractions, result.model_dump())
    return {
        "destination_context": destination_context,
        "research_output": result.model_dump(),
    }
