from Member_2_Researcher.attraction_tool import AttractionResult, DestinationContext
from Member_2_Researcher.attraction_tool import _is_excluded_place
from Member_2_Researcher.research_agent import AttractionRecommendation, ResearchOutput


def test_research_models_hold_expected_values() -> None:
    recommendation = AttractionRecommendation(
        name="Senso-ji",
        description="Historic Buddhist temple.",
        estimated_time_hours=2.5,
        interest_match="culture",
        source="https://example.com",
    )
    output = ResearchOutput(destination_summary="Tokyo is a large city.", attractions=[recommendation])
    assert output.destination_summary
    assert output.attractions[0].interest_match == "culture"


def test_destination_context_model_holds_expected_values() -> None:
    context = DestinationContext(
        destination="Kandy",
        display_name="Kandy, Sri Lanka",
        latitude=7.2906,
        longitude=80.6337,
        country="Sri Lanka",
    )
    assert context.destination == "Kandy"
    assert context.country == "Sri Lanka"


def test_attraction_result_model_requires_positive_time() -> None:
    result = AttractionResult(
        name="Temple of the Tooth",
        description="Historic religious site.",
        estimated_time_hours=2.0,
        interest_match="culture",
        source="https://example.com",
    )
    assert result.estimated_time_hours > 0


def test_research_tool_excludes_low_value_places() -> None:
    assert _is_excluded_place("Kandy Airport") is True
    assert _is_excluded_place("Colombo Fort Railway Station") is True
    assert _is_excluded_place("Temple of the Tooth") is False
