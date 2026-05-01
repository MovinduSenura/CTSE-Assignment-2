# AI Travel Planner System Explanation

## 1. System Purpose

This project is a **multi-agent travel planning system** that takes a user trip request and turns it into a reviewed itinerary. It is designed as a student assignment that demonstrates:

- agent decomposition
- structured LLM outputs
- tool-assisted reasoning
- workflow orchestration with LangGraph
- testing of both deterministic logic and data models

The system is currently scoped to **Sri Lanka travel planning**.

## 2. High-Level Architecture

The application is orchestrated from `main.py` using a `LangGraph` state graph.

The execution flow is:

1. `Planner`
2. `Researcher`
3. `Executor`
4. `Reviewer`

This is a **sequential pipeline**, meaning each agent depends on the previous agent's outputs.

## 3. Main Entry Point

The entry point is `main.py`.

It is responsible for:

- reading CLI arguments
- accepting either natural-language or structured trip input
- converting the request into a shared workflow state
- creating the Ollama LLM connection
- building the LangGraph pipeline
- running the graph
- printing the final itinerary
- writing execution logs

The main shared state is defined as `TravelPlannerState`, which contains fields such as:

- `destination`
- `budget`
- `days`
- `interests`
- `currency`
- `trace_id`
- `planner_output`
- `destination_context`
- `research_output`
- `budget_output`
- `reviewer_output`

## 4. Workflow State and Data Passing

Each stage adds new structured data into the shared state.

### Initial state

Created from CLI input:

- destination
- budget
- days
- interests
- currency
- trace ID

### After Planner

Adds:

- `planner_output`

### After Researcher

Adds:

- `destination_context`
- `research_output`

### After Executor

Adds:

- `budget_output`

### After Reviewer

Adds:

- `reviewer_output`

This design makes the workflow easy to inspect and easy to extend later.

## 5. Planner Agent

Files:

- `Member_1_Planner/planner_agent.py`
- `Member_1_Planner/validation_tool.py`

### Responsibility

The Planner Agent converts the user's request into a strict execution brief for downstream agents.

It does **not**:

- invent attractions
- estimate prices
- create the final itinerary

### Planner process

The planner first validates and normalizes the request using `validate_and_structure_trip_request()`.

This validation step:

- checks destination presence
- checks budget is greater than zero
- checks days are between `1` and `14`
- normalizes interest labels
- classifies budget tier as `low`, `medium`, or `high`
- classifies pacing as `relaxed`, `balanced`, or `packed`
- builds warnings and planning constraints

### Sri Lanka restriction

The planner enforces Sri Lanka-only support through `_ensure_sri_lanka_destination()`.

This works in two ways:

- obvious non-Sri Lankan destinations are blocked using a known list
- destination verification is done through `resolve_destination()` from the research tool

### Planner output

The planner produces a structured `PlannerOutput` model containing:

- normalized destination
- trip style
- user goal
- budget tier
- pacing
- task list
- research focus
- required budget checks
- planning constraints
- risk flags
- fallback notes
- planning notes

### Important safety behavior

If the planner LLM fails, the code creates a deterministic fallback output instead of stopping the whole pipeline.

The planner also sanitizes the LLM result so that:

- research focus only uses validated interests
- task assignments still mention `Researcher`, `Executor`, and `Reviewer`
- required budget checks stay fixed
- validated destination and pacing are preserved

## 6. Validation Tool

The validation tool is a key non-LLM part of the project.

### Natural-language parsing

`parse_trip_request()` extracts:

- days
- destination
- budget
- currency
- interests

from requests such as:

```text
Plan a 2-day trip to Kandy under 30000 for culture and food
```

This parser is intentionally narrow and rule-based. It is designed for predictable assignment behavior rather than broad natural-language understanding.

### Budget heuristics

Budget tier logic:

- For `LKR`:
  - below `10000` -> `low`
  - above `100000` -> `high`
  - otherwise -> `medium`
- For non-`LKR` currencies:
  - uses simple per-day thresholds

### Pacing heuristics

Trip pacing depends on:

- trip length
- number of interests

More interests in fewer days leads to a `packed` result.

### Warning generation

Warnings are added for cases such as:

- too many interests for a short trip
- very low budget
- overly packed itineraries

These warnings are passed forward so later agents can stay realistic.

## 7. Researcher Agent

Files:

- `Member_2_Researcher/research_agent.py`
- `Member_2_Researcher/attraction_tool.py`

### Responsibility

The Researcher Agent finds destination context and nearby attractions using external tools, then shapes that into structured output.

### Step 1: resolve destination

`resolve_destination()` uses the OpenStreetMap Nominatim API to retrieve:

- display name
- latitude
- longitude
- country

It explicitly restricts results to:

- country code `lk`
- country name `Sri Lanka`

So the researcher doubles as a location verification layer.

### Step 2: search attractions

`search_attractions()` uses Wikipedia geosearch near the destination coordinates.

For each nearby place, it:

- filters out low-value infrastructure-like results
- fetches a Wikipedia summary
- estimates visit time
- matches the place to one of the user interests
- stores the source URL

### Attraction filtering

The system excludes generic places like:

- airports
- stations
- banks
- hospitals
- schools

This reduces noisy travel results.

### Research output

The agent returns:

- a destination summary
- a list of structured attraction recommendations

Each attraction contains:

- name
- description
- estimated visit time
- interest match
- source

### Fallback and sanitization

If the research LLM fails:

- the system builds a deterministic summary from tool output

If the LLM invents attractions:

- `_sanitize_research_output()` removes unsupported ones and keeps only tool-derived attractions

This is one of the strongest anti-hallucination controls in the project.

## 8. Executor Agent

Files:

- `Member_3_Executor/executor_agent.py`
- `Member_3_Executor/budget_tool.py`
- `Member_3_Executor/destinations.json`

### Responsibility

The Executor Agent turns the researched plan into a cost estimate.

### Budget tool

The real cost calculation happens in `estimate_trip_budget()`.

It loads live Sri Lanka market references from public sources, such as:

- Numbeo city or country cost-of-living pages
- public exchange-rate APIs for currency conversion

The tool extracts values for:

- hotel per night
- food per day
- transport per day
- attraction cost per place

For Sri Lanka, the values are derived from the current public data returned by those pages and converted into the requested currency when needed.

### Budget calculation logic

The tool computes:

- accommodation = nightly rate x `max(days - 1, 1)`
- food = daily rate x days
- transport = daily rate x days
- attractions = price per place x number of attractions

It then returns:

- currency
- line items
- total estimated cost
- budget status
- summary

### Weak point

Unlike the Planner and Researcher, the Executor originally had **no fallback handling** around the LLM call. That was fixed so the deterministic tool output is returned if the LLM rewrite step fails.

That is an important design limitation in the current implementation.

## 9. Reviewer Agent

Files:

- `Member_4_Reviewer/reviewer_agent.py`
- `Member_4_Reviewer/formatter_tool.py`

### Responsibility

The Reviewer Agent checks whether the itinerary is complete, realistic, and aligned with the budget, then produces the final text shown to the user.

### Review audit

Before using the LLM, `audit_itinerary()` creates warnings if:

- there are not enough attractions for the number of days
- the trip is over budget
- the destination summary is missing

### Reviewer prompt requirements

The LLM is asked to produce:

- `approved`
- `warnings`
- `final_itinerary`

The final itinerary must include:

- a short overview
- day-by-day sections like `Day 1`, `Day 2`
- a budget summary

### Fallback formatting

If the LLM output does not look like a real itinerary, `_looks_like_real_itinerary()` rejects it.

Then the code uses `format_final_itinerary()` to deterministically build the output.

This is another strong reliability feature because the user still receives a usable result even if the LLM response is weak.

## 10. External Integrations

The system depends on:

- `Ollama` for the local LLM
- `OpenStreetMap Nominatim` for destination geocoding
- `Wikipedia API` for nearby attractions and summaries

These integrations make the project more realistic, but they also introduce runtime dependency on:

- internet access
- API availability
- response quality from public data sources

## 11. Logging

Logging is configured in `configure_logging()` in `main.py`.

Logs are written to:

- `logs/execution.log`

The log captures major workflow events such as:

- system start
- planner input and output
- research input and output
- executor output
- reviewer output

This is useful for demos, debugging, and assignment evaluation.

## 12. Testing Strategy

The project includes both unit tests and property-based tests.

### Planner tests

Planner tests check:

- natural-language parsing
- currency extraction
- validation rules
- Sri Lanka restriction
- task creation
- output contract shape

### Researcher tests

Research tests check:

- Pydantic model behavior
- exclusion rules for low-value places
- coordinate constraints

### Executor tests

Executor tests check:

- budget tool output structure
- positive total cost
- budget classification

### Reviewer tests

Reviewer tests check:

- over-budget warning generation
- itinerary formatting structure

### Property-based testing

`Hypothesis` is used mainly for:

- planner validation properties
- task generation properties
- research model properties

This improves confidence beyond a few hand-written examples.

## 13. Important Design Strengths

- Clear separation of responsibilities between agents
- Structured outputs with `Pydantic`
- LangGraph-based orchestration
- Good use of deterministic helper tools
- Multiple anti-hallucination protections
- Fallbacks in planner and reviewer stages
- Good test coverage for a student assignment

## 14. Important Design Limitations

- The system only supports Sri Lanka destinations
- The execution order is fully sequential
- Budget estimation is heuristic, not live-market based
- `.env` exists but is not actively loaded into runtime logic
- The Executor and Reviewer LLM calls are less defensive than the Planner and Researcher
- Attraction quality depends on Wikipedia geosearch relevance
- The natural-language parser only supports narrow request phrasing

## 15. End-to-End Example

For a request like:

```text
Plan a 2-day trip to Kandy under 30000 for culture and food
```

the system works like this:

1. `main.py` parses the request into structured fields.
2. The Planner validates Kandy, classifies budget and pace, and creates downstream tasks.
3. The Researcher resolves Kandy's coordinates and fetches nearby attractions from Wikipedia.
4. The Executor estimates accommodation, food, transport, and attraction costs.
5. The Reviewer checks completeness and creates the final day-by-day itinerary.
6. The final plan is printed to the console and execution details are logged.

## 16. Summary

This project is a well-structured educational example of a multi-agent AI system. Its main idea is not just "using an LLM," but combining:

- validation
- tools
- orchestration
- structured state
- fallbacks
- testing

to create a more reliable travel-planning workflow.

It is especially strong as an assignment submission because each member module has a distinct responsibility and the full system demonstrates integration across all four parts.
