"""Reviewer Agent implementation.

The Reviewer Agent is the final stage in the travel planning pipeline.
It performs quality assurance on the assembled itinerary by auditing
completeness, budget alignment, and interest coverage, then produces
the final formatted travel plan for the user.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from Member_4_Reviewer.formatter_tool import (
    AuditResult,
    audit_itinerary,
    format_final_itinerary,
    validate_itinerary_text,
)


class ReviewerOutput(BaseModel):
    """Structured output of the Reviewer Agent.

    Attributes:
        approved: Whether the itinerary passes quality review.
        approval_reason: Brief explanation of the approval or rejection decision.
        warnings: Quality issues found during audit and review.
        suggestions: Non-critical improvement ideas for the travel plan.
        completeness_score: Overall quality score from the audit tool (0.0-1.0).
        budget_aligned: Whether the estimated cost is within the user budget.
        final_itinerary: The complete formatted itinerary text for the user.
    """

    approved: bool
    approval_reason: str = Field(min_length=1)
    warnings: list[str]
    suggestions: list[str] = Field(default_factory=list)
    completeness_score: float = Field(ge=0.0, le=1.0)
    budget_aligned: bool
    final_itinerary: str = Field(min_length=1)


def run_reviewer_agent(state: dict, llm, logger: logging.Logger) -> dict:
    """Review the itinerary for completeness, realism, and budget alignment.

    This function orchestrates the Reviewer Agent workflow:
    1. Run the audit tool to produce deterministic quality findings.
    2. Build a detailed prompt with audit results and upstream outputs.
    3. Call the LLM for structured review and itinerary generation.
    4. Sanitize the LLM output to preserve audit-tool findings.
    5. Fall back to deterministic formatting if the LLM output is weak.

    Args:
        state: Shared workflow state containing planner_output, research_output,
            budget_output, destination, days, budget, interests, and currency.
        llm: The ChatOllama language model instance.
        logger: Logger for execution tracing.

    Returns:
        A dict with reviewer_output containing the ReviewerOutput data.
    """
    trace_id = state.get("trace_id", "unknown")

    # Step 1: Deterministic audit
    audit = audit_itinerary(
        research_output=state["research_output"],
        budget_output=state["budget_output"],
        days=state["days"],
        interests=state.get("interests"),
        budget_limit=state.get("budget"),
    )
    logger.info(
        "REVIEWER_AUDIT | trace=%s | audit=%s",
        trace_id,
        audit.model_dump_json(),
    )

    # Step 2: Build prompt
    prompt = _build_reviewer_prompt(state, audit)
    logger.info(
        "REVIEWER_INPUT | trace=%s | destination=%s | days=%s | budget=%s",
        trace_id,
        state.get("destination"),
        state.get("days"),
        state.get("budget"),
    )

    # Step 3: LLM call with fallback
    try:
        raw_result = llm.with_structured_output(ReviewerOutput).invoke(prompt)
        result = _sanitize_reviewer_output(raw_result, audit, state)
    except Exception as exc:
        logger.warning("REVIEWER_LLM_FALLBACK | trace=%s | error=%s", trace_id, exc)
        result = _build_fallback_output(state, audit)

    # Step 4: Validate itinerary structure and reformat if needed
    validation = validate_itinerary_text(result.final_itinerary, state["days"])
    if not validation.is_valid:
        logger.info(
            "REVIEWER_ITINERARY_REFORMAT | trace=%s | issues=%s",
            trace_id,
            json.dumps(validation.issues, ensure_ascii=False),
        )
        reformatted = format_final_itinerary(
            destination=state["destination"],
            days=state["days"],
            user_goal=state["planner_output"].get(
                "user_goal",
                f"Visit {state['destination']}.",
            ),
            attractions=state["research_output"]["attractions"],
            budget_output=state["budget_output"],
            budget_summary=state["budget_output"]["summary"],
            warnings=result.warnings or audit.warnings,
            suggestions=result.suggestions or audit.suggestions,
        )
        result = result.model_copy(update={"final_itinerary": reformatted})

    logger.info(
        "REVIEWER_OUTPUT | trace=%s | approved=%s | score=%s | warnings=%s",
        trace_id,
        result.approved,
        result.completeness_score,
        json.dumps(result.warnings, ensure_ascii=False),
    )
    return {"reviewer_output": result.model_dump()}


def _build_reviewer_prompt(state: dict, audit: AuditResult) -> str:
    """Build the reviewer prompt with strict quality assurance rules.

    Args:
        state: Shared workflow state with all upstream outputs.
        audit: Deterministic audit results from the formatter tool.

    Returns:
        A formatted prompt string for the LLM.
    """
    return f"""
You are the Reviewer Agent in a local travel-planning multi-agent system.
Your role is to perform a final quality assurance review of the travel
itinerary before it is presented to the user.

Your review responsibilities:
1. Verify the itinerary is complete with a plan for each requested day.
2. Verify the budget estimate is realistic and aligns with the user budget.
3. Verify attractions are relevant to the user's stated interests.
4. Identify any gaps, inconsistencies, or unrealistic elements.
5. Produce the final formatted itinerary for the user.

Planner output:
{state['planner_output']}

Research output:
{state['research_output']}

Budget output:
{state['budget_output']}

Audit findings from tool:
Warnings: {audit.warnings}
Suggestions: {audit.suggestions}
Completeness score: {audit.completeness_score}
Interest coverage: {audit.interest_coverage}
Budget aligned: {audit.budget_aligned}

Return:
- approved: whether the itinerary passes quality review
- approval_reason: brief explanation of the approval decision
- warnings: list of quality issues found
- suggestions: list of improvement ideas
- completeness_score: use the value {audit.completeness_score} from the audit tool
- budget_aligned: use the value {audit.budget_aligned} from the audit tool
- final_itinerary: the complete formatted itinerary text

Rules:
- final_itinerary must begin with a short overview paragraph
- final_itinerary must include day-by-day sections using labels Day 1, Day 2
- final_itinerary must include a Budget Summary section
- final_itinerary should include a budget breakdown by category when available
- do not invent new attractions beyond what the Research Agent found
- do not change cost numbers from the Budget output
- use only attraction names exactly as provided in the Research output
- include all audit warnings in the warnings list
- set approved to false if completeness_score is below 0.5 or the trip is over budget
- do not return a generic approval paragraph as the final_itinerary
"""


def _build_fallback_output(state: dict, audit: AuditResult) -> ReviewerOutput:
    """Build a deterministic fallback when the LLM fails.

    Args:
        state: Shared workflow state with all upstream outputs.
        audit: Deterministic audit results from the formatter tool.

    Returns:
        A ReviewerOutput built entirely from tool outputs.
    """
    approved = audit.completeness_score >= 0.5 and audit.budget_aligned
    approval_reason = (
        "Itinerary meets minimum quality thresholds."
        if approved
        else "Itinerary has quality issues that need attention."
    )

    itinerary = format_final_itinerary(
        destination=state["destination"],
        days=state["days"],
        user_goal=state["planner_output"].get(
            "user_goal",
            f"Visit {state['destination']}.",
        ),
        attractions=state["research_output"]["attractions"],
        budget_output=state["budget_output"],
        budget_summary=state["budget_output"]["summary"],
        warnings=audit.warnings,
        suggestions=audit.suggestions,
    )

    return ReviewerOutput(
        approved=approved,
        approval_reason=approval_reason,
        warnings=audit.warnings,
        suggestions=audit.suggestions,
        completeness_score=audit.completeness_score,
        budget_aligned=audit.budget_aligned,
        final_itinerary=itinerary,
    )


def _sanitize_reviewer_output(
    output: ReviewerOutput,
    audit: AuditResult,
    state: dict,
) -> ReviewerOutput:
    """Clamp reviewer output to audit-tool findings to reduce hallucinations.

    The LLM may override the tool-computed completeness score, ignore audit
    warnings, or invent new attraction names.  This function forces the
    structured fields to stay consistent with the deterministic audit.

    Args:
        output: Raw LLM-produced ReviewerOutput.
        audit: Deterministic audit results from the formatter tool.
        state: Shared workflow state.

    Returns:
        A sanitized ReviewerOutput with audit values preserved.
    """
    # Merge audit warnings with any LLM-generated warnings
    merged_warnings = list(audit.warnings)
    for warning in output.warnings:
        if warning not in merged_warnings:
            merged_warnings.append(warning)

    # Merge suggestions
    merged_suggestions = list(audit.suggestions)
    for suggestion in output.suggestions:
        if suggestion not in merged_suggestions:
            merged_suggestions.append(suggestion)

    # Force completeness_score and budget_aligned from the audit tool
    sanitized_approved = (
        audit.completeness_score >= 0.5 and audit.budget_aligned
    )

    return ReviewerOutput(
        approved=sanitized_approved,
        approval_reason=output.approval_reason or (
            "Itinerary meets minimum quality thresholds."
            if sanitized_approved
            else "Itinerary has quality issues that need attention."
        ),
        warnings=merged_warnings,
        suggestions=merged_suggestions,
        completeness_score=audit.completeness_score,
        budget_aligned=audit.budget_aligned,
        final_itinerary=output.final_itinerary,
    )
