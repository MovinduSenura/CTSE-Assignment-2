# Member_4_Reviewer

This folder contains Member 4's work on the **Reviewer Agent**.

## Agent

- `reviewer_agent.py` — The Reviewer Agent performs the final quality assurance
  review of the travel itinerary. It audits completeness, budget alignment, and
  interest coverage, then produces the final formatted travel plan for the user.
  The agent uses a structured Pydantic output model with 7 typed fields, includes
  LLM fallback handling and output sanitization to prevent hallucinations.

## Tool

- `formatter_tool.py` — Provides three deterministic helper functions:
  - `audit_itinerary()` — Runs 7 quality checks (attraction count, budget, summary,
    interest coverage, pacing, source URLs, budget utilization) and returns a
    structured `AuditResult` with a completeness score.
  - `validate_itinerary_text()` — Validates the structure of a formatted itinerary
    (overview, day markers, budget summary) and returns an `ItineraryValidationResult`.
  - `format_final_itinerary()` — Builds a deterministic fallback itinerary when the
    LLM output is structurally invalid.

## Tests

- `test_reviewer.py` — 24 unit tests covering audit checks, validation, formatting,
  error handling, and output model contracts.
- `test_reviewer_property.py` — Hypothesis property-based tests verifying that audit
  results are always bounded, formatters never crash, and validators handle arbitrary input.

## Evaluation

- `evaluate_reviewer.py` — Standalone evaluation harness with deterministic assertions
  across the full audit → format → validate → model pipeline.
- `evaluate_reviewer_property.py` — Property-based evaluation harness wrapper.
