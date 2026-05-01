from Member_3_Executor.budget_tool import estimate_trip_budget


class FakeResponse:
    def __init__(self, *, text: str = "", json_payload: dict | None = None, status_code: int = 200):
        self.text = text
        self._json_payload = json_payload or {}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self) -> dict:
        return self._json_payload


def test_executor_budget_tool_uses_live_sri_lanka_prices(monkeypatch) -> None:
    context = {
        "destination": "Colombo",
        "display_name": "Colombo, Sri Lanka",
        "latitude": 6.9271,
        "longitude": 79.8612,
        "country": "Sri Lanka",
    }

    city_page = """
        Meal at an Inexpensive Restaurant ₨1,400.00
        Bottled Water (0.33 Liter) ₨90.00
        One-Way Ticket (Local Transport) ₨50.00
        Taxi 1 km (Standard Tariff) ₨120.00
        1 Bedroom Apartment Outside of City Centre ₨90,000.00
        Cinema Ticket (International Release) ₨1,400.00
    """

    def fake_get(url, *args, **kwargs):
        if "numbeo.com/cost-of-living/in/" in url:
            return FakeResponse(text=city_page)
        if "frankfurter.app" in url:
            return FakeResponse(json_payload={"rates": {"USD": 0.0033}})
        raise AssertionError(f"Unexpected URL called: {url}")

    monkeypatch.setattr("Member_3_Executor.budget_tool.requests.get", fake_get)

    result = estimate_trip_budget(context, days=3, budget_limit=120000.0, attraction_count=4, currency="LKR")

    assert result["total_estimated_cost"] == 24800.0
    assert result["budget_status"] == "within budget"
    assert result["data_source"].startswith("Numbeo city prices")
    assert len(result["line_items"]) == 4


def test_executor_budget_tool_falls_back_when_live_sources_fail(monkeypatch) -> None:
    context = {
        "destination": "Kandy",
        "display_name": "Kandy, Sri Lanka",
        "latitude": 7.2906,
        "longitude": 80.6337,
        "country": "Sri Lanka",
    }

    def fake_get(url, *args, **kwargs):
        if "numbeo.com" in url:
            return FakeResponse(
                text="""
                    Meal at an Inexpensive Restaurant ₨1,200.00
                    Bottled Water (0.33 Liter) ₨75.00
                    One-Way Ticket (Local Transport) ₨40.00
                    Taxi 1 km (Standard Tariff) ₨100.00
                    1 Bedroom Apartment Outside of City Centre ₨70,000.00
                    Cinema Ticket (International Release) ₨1,200.00
                """
            )
        if "open.er-api.com/v6/latest/LKR" in url:
            return FakeResponse(json_payload={"rates": {"USD": 0.0032}})
        raise AssertionError(f"Unexpected URL called: {url}")

    monkeypatch.setattr("Member_3_Executor.budget_tool.requests.get", fake_get)

    result = estimate_trip_budget(context, days=2, budget_limit=150.0, attraction_count=2, currency="USD")

    assert result["total_estimated_cost"] > 0
    assert result["budget_status"] == "within budget"
    assert result["data_source"].startswith("Numbeo")
    assert result["currency"] == "USD"
