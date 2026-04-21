"""CLI and orchestration entry point for the AI Travel Planner."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import TypedDict
from uuid import uuid4

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from Member_1_Planner.validation_tool import parse_trip_request
from Member_1_Planner.planner_agent import run_planner_agent
from Member_2_Researcher.research_agent import run_research_agent
from Member_3_Executor.executor_agent import run_executor_agent
from Member_4_Reviewer.reviewer_agent import run_reviewer_agent


class TravelPlannerState(TypedDict, total=False):
    destination: str
    budget: float
    days: int
    interests: list[str]
    currency: str
    trace_id: str
    planner_output: dict
    destination_context: dict
    research_output: dict
    budget_output: dict
    reviewer_output: dict


def configure_logging() -> logging.Logger:
    """Configure application logging."""
    logger = logging.getLogger("ai_travel_planner")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.FileHandler("logs/execution.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


def get_llm(model_name: str = "llama3:latest") -> ChatOllama:
    """Create the Ollama chat model used by all agents."""
    return ChatOllama(model=model_name, temperature=0.2)


def build_graph(llm: ChatOllama, logger: logging.Logger):
    """Build the sequential LangGraph workflow."""
    workflow = StateGraph(TravelPlannerState)
    workflow.add_node("planner", lambda state: run_planner_agent(state, llm, logger))
    workflow.add_node("research", lambda state: run_research_agent(state, llm, logger))
    workflow.add_node("executor", lambda state: run_executor_agent(state, llm, logger))
    workflow.add_node("reviewer", lambda state: run_reviewer_agent(state, llm, logger))
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "research")
    workflow.add_edge("research", "executor")
    workflow.add_edge("executor", "reviewer")
    workflow.add_edge("reviewer", END)
    return workflow.compile()


def run_system(
    destination: str,
    budget: float,
    days: int,
    interests: list[str],
    currency: str = "LKR",
    llm: ChatOllama | None = None,
) -> TravelPlannerState:
    """Run the whole multi-agent travel planning system."""
    logger = configure_logging()
    llm_instance = llm or get_llm()
    graph = build_graph(llm_instance, logger)
    initial_state: TravelPlannerState = {
        "destination": destination,
        "budget": budget,
        "days": days,
        "interests": interests,
        "currency": currency,
        "trace_id": uuid4().hex,
    }
    logger.info("SYSTEM_START | %s", initial_state)
    final_state = graph.invoke(initial_state)
    logger.info("SYSTEM_END | %s", final_state.get("reviewer_output", {}))
    return final_state


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run the AI Travel Planner.")
    parser.add_argument("--request", help="Natural-language request, for example 'Plan a 2-day trip to Kandy under 30000 for culture and food'")
    parser.add_argument("--destination", help="Trip destination, for example 'Tokyo'")
    parser.add_argument("--budget", type=float, help="Maximum trip budget")
    parser.add_argument("--days", type=int, help="Number of trip days")
    parser.add_argument("--currency", default="LKR", help="Budget currency")
    parser.add_argument("--interests", nargs="+", help="Interests, for example culture food anime")
    parser.add_argument("--show-planner-details", action="store_true", help="Print planner output for demos and evaluation")
    return parser.parse_args()


def resolve_user_input(args: argparse.Namespace) -> dict:
    """Resolve CLI arguments into a single structured input object."""
    if args.request:
        parsed_request = parse_trip_request(args.request).model_dump()
        if "currency" not in parsed_request or not parsed_request["currency"]:
            parsed_request["currency"] = args.currency
        return parsed_request

    missing = [
        name
        for name, value in {
            "destination": args.destination,
            "budget": args.budget,
            "days": args.days,
            "interests": args.interests,
        }.items()
        if value is None
    ]
    if missing:
        raise ValueError(f"Missing required inputs: {', '.join(missing)}")

    return {
        "destination": args.destination,
        "budget": args.budget,
        "days": args.days,
        "currency": args.currency,
        "interests": args.interests,
    }


def main() -> None:
    """CLI runner."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    structured_input = resolve_user_input(args)
    print("\n=== STRUCTURED INPUT ===\n")
    print(json.dumps(structured_input, indent=4))
    final_state = run_system(
        destination=structured_input["destination"],
        budget=structured_input["budget"],
        days=structured_input["days"],
        interests=structured_input["interests"],
        currency=structured_input.get("currency", args.currency),
    )
    if args.show_planner_details:
        print("\n=== PLANNER OUTPUT ===\n")
        print(json.dumps(final_state["planner_output"], indent=4))
    print("\n=== FINAL TRAVEL PLAN ===\n")
    print(final_state["reviewer_output"]["final_itinerary"])
    print("\nExecution log: logs/execution.log")


if __name__ == "__main__":
    main()
