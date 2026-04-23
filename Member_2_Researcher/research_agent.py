"""Research Agent implementation."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from Member_2_Researcher.attraction_tool import AttractionResult, DestinationContext, resolve_destination, search_attractions


class AttractionRecommendation(BaseModel):
    """Structured recommendation returned by the Researcher Agent."""

    name: str
    description: str
    estimated_time_hours: float = Field(gt=0)
    interest_match: str
    source: str
    distance_meters: int | None = None
    relevance_score: float = Field(default=0.0, ge=0)


class ResearchOutput(BaseModel):
    """Structured output of the Researcher Agent."""

    destination_summary: str
    attractions: list[AttractionRecommendation] = Field(min_length=1)


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
{[item.model_dump() for item in attractions]}

Return:
- destination_summary
- attractions

Rules:
- use only the provided destination context and attraction list
- do not invent attractions not present in the tool output
- keep attraction names exactly as provided by the tool
"""
    try:
        raw_result = llm.with_structured_output(ResearchOutput).invoke(prompt)
        result = _sanitize_research_output(raw_result, destination_context, attractions)
    except Exception as exc:
        logger.warning("RESEARCH_LLM_FALLBACK | %s", exc)
        result = _build_fallback_research_output(destination_context, attractions)

    logger.info("RESEARCH_INPUT | %s", json.dumps(state, ensure_ascii=False, default=str))
    logger.info("RESEARCH_DESTINATION | %s", destination_context.model_dump_json())
    logger.info("RESEARCH_TOOL_OUTPUT | %s", json.dumps([item.model_dump() for item in attractions], ensure_ascii=False))
    logger.info("RESEARCH_OUTPUT | %s", result.model_dump_json())
    return {
        "destination_context": destination_context.model_dump(),
        "research_output": result.model_dump(),
    }


def _build_fallback_research_output(
    destination_context: DestinationContext,
    attractions: list[AttractionResult],
) -> ResearchOutput:
    """Build deterministic research output if LLM generation fails."""
    return ResearchOutput(
        destination_summary=(
            f"{destination_context.destination} is located in {destination_context.country}. "
            "The destination summary is based only on tool-resolved location and nearby attractions."
        ),
        attractions=[
            AttractionRecommendation(**item.model_dump())
            for item in attractions
        ],
    )


def _sanitize_research_output(
    output: ResearchOutput,
    destination_context: DestinationContext,
    attractions: list[AttractionResult],
) -> ResearchOutput:
    """Restrict final research output to tool-supported attractions only."""
    allowed = {item.name: item for item in attractions}
    sanitized_attractions: list[AttractionRecommendation] = []
    for attraction in output.attractions:
        if attraction.name in allowed:
            sanitized_attractions.append(AttractionRecommendation(**allowed[attraction.name].model_dump()))

    if not sanitized_attractions:
        sanitized_attractions = [AttractionRecommendation(**item.model_dump()) for item in attractions]

    summary = output.destination_summary.strip()
    if not summary:
        summary = (
            f"{destination_context.destination} is located in {destination_context.country}. "
            "The destination summary is based only on validated research tool output."
        )

    return ResearchOutput(destination_summary=summary, attractions=sanitized_attractions)
