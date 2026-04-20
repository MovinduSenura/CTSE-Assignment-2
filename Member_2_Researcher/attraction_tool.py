"""Attraction research tool using public endpoints."""

from __future__ import annotations

from typing import Any

import requests
from requests.utils import quote


USER_AGENT = "ai-travel-planner/0.1 (student assignment project)"


def resolve_destination(destination: str, timeout: int = 15) -> dict:
    """Resolve a destination into coordinates and country data."""
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": destination,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
            "accept-language": "en",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload:
        raise ValueError(f"Could not resolve destination '{destination}'.")

    first = payload[0]
    address = first.get("address", {})
    return {
        "destination": destination,
        "display_name": first["display_name"],
        "latitude": float(first["lat"]),
        "longitude": float(first["lon"]),
        "country": address.get("country", "Unknown"),
    }


def search_attractions(context: dict, interests: list[str], limit: int = 8, timeout: int = 15) -> list[dict]:
    """Find nearby attractions using Wikimedia geosearch and summaries."""
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{context['latitude']}|{context['longitude']}",
            "gsradius": 10000,
            "gslimit": limit * 2,
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    places: list[dict[str, Any]] = response.json().get("query", {}).get("geosearch", [])

    recommendations: list[dict] = []
    for place in places:
        if len(recommendations) >= limit:
            break
        title = place.get("title", "")
        summary = _fetch_summary(title, timeout)
        if not summary:
            continue
        recommendations.append(
            {
                "name": title,
                "description": summary,
                "estimated_time_hours": _estimate_visit_time(summary),
                "interest_match": _pick_interest(title, interests),
                "source": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            }
        )

    if not recommendations:
        raise ValueError(f"No attraction data found for '{context['destination']}'.")

    return recommendations


def _fetch_summary(title: str, timeout: int) -> str:
    response = requests.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}",
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    if response.status_code != 200:
        return ""
    return str(response.json().get("extract", "")).strip()


def _pick_interest(title: str, interests: list[str]) -> str:
    lowered = title.lower()
    for interest in interests:
        if interest.lower() in lowered:
            return interest
    return interests[0] if interests else "general sightseeing"


def _estimate_visit_time(summary: str) -> float:
    lowered = summary.lower()
    if "museum" in lowered or "park" in lowered or "temple" in lowered:
        return 2.5
    if "tower" in lowered or "market" in lowered:
        return 1.5
    return 2.0

