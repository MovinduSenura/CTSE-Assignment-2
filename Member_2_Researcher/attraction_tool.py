"""Attraction research tool using public endpoints."""

from __future__ import annotations

from typing import Any

import requests
from pydantic import BaseModel, Field
from requests.utils import quote


USER_AGENT = "ai-travel-planner/0.1 (student assignment project)"
SRI_LANKA_COUNTRY_CODE = "lk"
EXCLUDED_KEYWORDS = {
    "airport",
    "station",
    "library",
    "office",
    "building",
    "bank",
    "hospital",
    "school",
    "college",
    "university",
}


class DestinationContext(BaseModel):
    """Resolved destination information used by the Researcher Agent."""

    destination: str
    display_name: str
    latitude: float
    longitude: float
    country: str


class AttractionResult(BaseModel):
    """Structured attraction data returned by the research tool."""

    name: str
    description: str
    estimated_time_hours: float = Field(gt=0)
    interest_match: str
    source: str


def resolve_destination(destination: str, timeout: int = 15) -> DestinationContext:
    """Resolve a destination into coordinates and country data.

    Args:
        destination: User-requested destination.
        timeout: Maximum request timeout in seconds.

    Returns:
        Structured destination metadata from Nominatim.

    Raises:
        ValueError: If the destination is empty or no result is found.
        requests.RequestException: If the API request fails.
    """
    normalized_destination = destination.strip()
    if not normalized_destination:
        raise ValueError("Destination is required for research.")

    query = normalized_destination
    if "sri lanka" not in normalized_destination.lower():
        query = f"{normalized_destination}, Sri Lanka"

    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
            "accept-language": "en",
            "countrycodes": SRI_LANKA_COUNTRY_CODE,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload:
        raise ValueError(f"Could not resolve destination '{normalized_destination}'.")

    first = payload[0]
    address = first.get("address", {})
    country = address.get("country", "Unknown")
    if country != "Sri Lanka":
        raise ValueError(f"Destination '{normalized_destination}' is outside Sri Lanka.")

    return DestinationContext(
        destination=normalized_destination,
        display_name=first["display_name"],
        latitude=float(first["lat"]),
        longitude=float(first["lon"]),
        country=country,
    )


def search_attractions(
    context: DestinationContext,
    interests: list[str],
    limit: int = 8,
    timeout: int = 15,
) -> list[AttractionResult]:
    """Find nearby attractions using Wikimedia geosearch and summaries.

    Args:
        context: Destination metadata from `resolve_destination`.
        interests: User interests used for simple attraction matching.
        limit: Maximum number of attractions to return.
        timeout: Maximum request timeout in seconds.

    Returns:
        A list of structured attraction recommendations.

    Raises:
        ValueError: If no attractions can be found.
        requests.RequestException: If the API request fails.
    """
    if limit <= 0:
        raise ValueError("Attraction search limit must be greater than zero.")

    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{context.latitude}|{context.longitude}",
            "gsradius": 10000,
            "gslimit": limit * 2,
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    places: list[dict[str, Any]] = response.json().get("query", {}).get("geosearch", [])

    recommendations: list[AttractionResult] = []
    for place in places:
        if len(recommendations) >= limit:
            break
        title = place.get("title", "")
        if _is_excluded_place(title):
            continue
        summary = _fetch_summary(title, timeout)
        if not summary:
            continue
        if _is_excluded_place(summary):
            continue
        recommendations.append(
            AttractionResult(
                name=title,
                description=summary,
                estimated_time_hours=_estimate_visit_time(summary),
                interest_match=_pick_interest(title, interests),
                source=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            )
        )

    if not recommendations:
        raise ValueError(f"No attraction data found for '{context.destination}'.")

    return recommendations


def _fetch_summary(title: str, timeout: int) -> str:
    """Fetch a short summary for a Wikipedia page title."""
    response = requests.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}",
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    if response.status_code != 200:
        return ""
    return str(response.json().get("extract", "")).strip()


def _pick_interest(title: str, interests: list[str]) -> str:
    """Pick the best matching user interest for a title."""
    lowered = title.lower()
    for interest in interests:
        if interest.lower() in lowered:
            return interest
    return interests[0] if interests else "general sightseeing"


def _estimate_visit_time(summary: str) -> float:
    """Estimate attraction visit time using simple category heuristics."""
    lowered = summary.lower()
    if "museum" in lowered or "park" in lowered or "temple" in lowered:
        return 2.5
    if "tower" in lowered or "market" in lowered:
        return 1.5
    return 2.0


def _is_excluded_place(text: str) -> bool:
    """Return True for generic infrastructure or low-value tourism results."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in EXCLUDED_KEYWORDS)
