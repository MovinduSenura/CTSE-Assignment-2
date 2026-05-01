import logging

from Member_3_Executor.executor_agent import run_executor_agent


class DummyResult:
    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return self._data


class DummyWrapper:
    def __init__(self, result):
        self._result = result

    def invoke(self, prompt):
        return self._result


class DummyLLM:
    def __init__(self, wrapper):
        self._wrapper = wrapper

    def with_structured_output(self, schema):
        return self._wrapper


def test_run_executor_with_researcher_budget():
    state = {
        "destination_context": {"destination": "Colombo", "country": "Sri Lanka"},
        "days": 3,
        "budget": 500.0,
        "currency": "LKR",
        "research_output": {"attractions": [{}, {}], "suggested_budget": 400.0},
    }

    # Construct a plausible ExecutorOutput-like dict the LLM would return
    tool_output = {
        "currency": "LKR",
        "line_items": [
            {"category": "Accommodation", "amount": 110.0, "reasoning": "x"},
            {"category": "Food", "amount": 42.0, "reasoning": "x"},
            {"category": "Transport", "amount": 24.0, "reasoning": "x"},
            {"category": "Attractions", "amount": 20.0, "reasoning": "x"},
        ],
        "total_estimated_cost": 196.0,
        "budget_status": "within budget",
        "summary": "Estimated LKR 196.00...",
        "researcher_budget": 400.0,
        "researcher_budget_status": "within researcher budget",
    }

    dummy = DummyResult(tool_output)
    wrapper = DummyWrapper(dummy)
    llm = DummyLLM(wrapper)

    out = run_executor_agent(state, llm, logging.getLogger("test"))
    assert "budget_output" in out
    bo = out["budget_output"]
    assert bo["total_estimated_cost"] == 196.0
    assert bo["researcher_budget"] == 400.0
    assert bo["researcher_budget_status"] in ("within researcher budget", "over researcher budget")


class FailingWrapper:
    def invoke(self, prompt):
        raise RuntimeError("LLM unavailable")


class FailingLLM:
    def with_structured_output(self, schema):
        return FailingWrapper()


def test_run_executor_falls_back_to_tool_output_when_llm_fails():
    state = {
        "destination_context": {"destination": "Colombo", "country": "Sri Lanka"},
        "days": 2,
        "budget": 100000.0,
        "currency": "LKR",
        "research_output": {"attractions": [{}, {}], "suggested_budget": 50000.0},
    }

    out = run_executor_agent(state, FailingLLM(), logging.getLogger("test"))
    assert "budget_output" in out
    bo = out["budget_output"]
    assert bo["total_estimated_cost"] > 0
    assert bo["researcher_budget"] == 50000.0
    assert bo["researcher_budget_status"] in ("within researcher budget", "over researcher budget")
