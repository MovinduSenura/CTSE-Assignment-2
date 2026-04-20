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
