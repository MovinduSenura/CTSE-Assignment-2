"""CLI and orchestration entry point for the AI Travel Planner."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TypedDict
from uuid import uuid4

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

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
    currency: str = "USD",
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
    parser.add_argument("--destination", required=True, help="Trip destination, for example 'Tokyo'")
    parser.add_argument("--budget", required=True, type=float, help="Maximum trip budget")
    parser.add_argument("--days", required=True, type=int, help="Number of trip days")
    parser.add_argument("--currency", default="USD", help="Budget currency")
    parser.add_argument("--interests", nargs="+", required=True, help="Interests, for example culture food anime")
    return parser.parse_args()


def main() -> None:
    """CLI runner."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    final_state = run_system(
        destination=args.destination,
        budget=args.budget,
        days=args.days,
        interests=args.interests,
        currency=args.currency,
    )
    print("\n=== FINAL TRAVEL PLAN ===\n")
    print(final_state["reviewer_output"]["final_itinerary"])
    print("\nExecution log: logs/execution.log")


if __name__ == "__main__":
    main()
