"""Budget calculation tool powered by live Sri Lanka market references."""

from __future__ import annotations

import html
import re

import requests


NUMBEO_USER_AGENT = "ai-travel-planner/0.1 (student assignment project)"
DEFAULT_TIMEOUT_SECONDS = 8


def estimate_trip_budget(
    destination_context: dict,
    days: int,
    budget_limit: float,
    attraction_count: int,
    currency: str = "USD",
) -> dict:
    """Estimate a trip budget using live Sri Lanka market references."""
    # Enforce Sri Lanka-only support
    country = destination_context.get("country")
    if country is None or country.strip().lower() != "sri lanka":
        raise ValueError("Executor budget estimation supports Sri Lanka destinations only.")

    profile = _load_live_sri_lanka_profile(destination_context)

    nights = max(days - 1, 1)
    hotel_total_lkr = round(profile["hotel_per_night"] * nights, 2)
    food_total_lkr = round(profile["food_per_day"] * days, 2)
    transport_total_lkr = round(profile["transport_per_day"] * days, 2)
    attraction_total_lkr = round(profile["attraction_per_place"] * attraction_count, 2)

    target_currency = (currency or "LKR").upper()
    exchange_rate = _get_exchange_rate("LKR", target_currency)

    hotel_total = round(hotel_total_lkr * exchange_rate, 2)
    food_total = round(food_total_lkr * exchange_rate, 2)
    transport_total = round(transport_total_lkr * exchange_rate, 2)
    attraction_total = round(attraction_total_lkr * exchange_rate, 2)

    line_items = [
        {
            "category": "Accommodation",
            "amount": hotel_total,
            "reasoning": f"Derived from live Sri Lanka price references ({profile['source']}).",
        },
        {
            "category": "Food",
            "amount": food_total,
            "reasoning": "Estimated from current restaurant and grocery references.",
        },
        {
            "category": "Transport",
            "amount": transport_total,
            "reasoning": "Estimated from current local transport and taxi references.",
        },
        {
            "category": "Attractions",
            "amount": attraction_total,
            "reasoning": "Estimated entry-ticket allowance per recommended place.",
        },
    ]

    total = round(sum(item["amount"] for item in line_items), 2)
    status = "within budget" if total <= budget_limit else "over budget"
    summary = (
        f"Estimated {target_currency} {total:.2f} for {days} days in {destination_context['destination']}. "
        f"The trip is {status} against the user budget of {target_currency} {budget_limit:.2f}. "
        f"Data source: {profile['source']}."
    )

    return {
        "currency": target_currency,
        "line_items": line_items,
        "total_estimated_cost": total,
        "budget_status": status,
        "summary": summary,
        "data_source": profile["source"],
        "exchange_rate_from_lkr": round(exchange_rate, 6),
    }


def _load_live_sri_lanka_profile(destination_context: dict) -> dict:
    """Load a budget profile from live sources, with safe fallback."""
    destination = destination_context.get("destination", "")
    city_profile = _try_numbeo_city_profile(destination)
    if city_profile:
        return city_profile

    country_profile = _try_numbeo_country_profile()
    if country_profile:
        return country_profile

    raise ValueError("Could not load live Sri Lanka budget data from public sources.")


def _try_numbeo_city_profile(destination: str) -> dict | None:
    """Build a city-specific profile from Numbeo cost-of-living pages."""
    normalized = destination.strip()
    if not normalized:
        return None

    slug = normalized.replace(",", " ").replace("/", " ").strip().replace(" ", "-")
    if "sri-lanka" not in slug.lower():
        slug = f"{slug}-Sri-Lanka"

    base_url = f"https://www.numbeo.com/cost-of-living/in/{slug}"
    text = _download_page_text(base_url)
    if not text:
        return None

    if "cannot find city id" in text.lower():
        suggested_url = _extract_suggested_numbeo_city_url(text)
        if suggested_url:
            text = _download_page_text(suggested_url)
            if not text:
                return None
            base_url = suggested_url

    extracted = _extract_numbeo_price_points(text)
    if not extracted:
        return None

    profile = _profile_from_numbeo_points(extracted, source=f"Numbeo city prices ({base_url})")
    return profile


def _try_numbeo_country_profile() -> dict | None:
    """Build a country-level Sri Lanka profile from Numbeo when city data is unavailable."""
    url = "https://www.numbeo.com/cost-of-living/country_result.jsp?country=Sri+Lanka"
    text = _download_page_text(url)
    if not text:
        return None
    extracted = _extract_numbeo_price_points(text)
    if not extracted:
        return None
    return _profile_from_numbeo_points(extracted, source=f"Numbeo Sri Lanka averages ({url})")


def _download_page_text(url: str) -> str | None:
    """Download a web page and normalize HTML into searchable plain text."""
    try:
        response = requests.get(
            url,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={"User-Agent": NUMBEO_USER_AGENT},
        )
        response.raise_for_status()
    except Exception:
        return None

    raw = response.text
    without_tags = re.sub(r"<[^>]+>", " ", raw)
    cleaned = html.unescape(without_tags)
    return re.sub(r"\s+", " ", cleaned)


def _extract_suggested_numbeo_city_url(text: str) -> str | None:
    """Extract suggested Numbeo city URL if the direct city slug did not resolve."""
    match = re.search(r"https://www\.numbeo\.com/cost-of-living/in/[A-Za-z0-9\-]+-Sri-Lanka", text)
    if not match:
        return None
    return match.group(0)


def _extract_numbeo_price_points(text: str) -> dict[str, float]:
    """Extract key Sri Lanka market prices from normalized Numbeo page text."""
    wanted_labels = {
        "meal_inexpensive": ["Meal at an Inexpensive Restaurant"],
        "water_small": ["Bottled Water (0.33 Liter)", "Bottled Water (1.5 Liter)"],
        "one_way_transport": ["One-Way Ticket (Local Transport)"],
        "taxi_1km": ["Taxi 1 km (Standard Tariff)"],
        "rent_outside_1br": ["1 Bedroom Apartment Outside of City Centre"],
        "cinema_ticket": ["Cinema Ticket (International Release)"],
    }

    extracted: dict[str, float] = {}
    for key, labels in wanted_labels.items():
        value = None
        for label in labels:
            value = _extract_price_for_label(text, label)
            if value is not None:
                break
        if value is not None:
            extracted[key] = value
    return extracted


def _extract_price_for_label(text: str, label: str) -> float | None:
    """Extract first numeric price value located after a given label."""
    pattern = rf"{re.escape(label)}\s*(?:Rs\.?\s*|LKR\s*|₨\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _profile_from_numbeo_points(points: dict[str, float], source: str) -> dict | None:
    """Convert extracted market points into a daily trip-cost profile (LKR)."""
    meal = points.get("meal_inexpensive")
    water = points.get("water_small", 0.0)
    one_way = points.get("one_way_transport")
    taxi_1km = points.get("taxi_1km")
    rent_outside = points.get("rent_outside_1br")
    cinema_ticket = points.get("cinema_ticket")

    # Need at least accommodation and transport signals to be meaningful.
    if rent_outside is None:
        return None
    if one_way is None and taxi_1km is None:
        return None

    hotel_per_night = round((rent_outside / 30.0) * 1.3, 2)

    if meal is None:
        food_per_day = None
    else:
        food_per_day = round((meal * 2.0) + (water * 2.0), 2)

    if one_way is not None and taxi_1km is not None:
        transport_per_day = round((one_way * 2.0) + (taxi_1km * 6.0), 2)
    elif one_way is not None:
        transport_per_day = round(one_way * 6.0, 2)
    elif taxi_1km is not None:
        transport_per_day = round(taxi_1km * 8.0, 2)
    else:
        return None

    attraction_per_place = round(cinema_ticket or 0.0, 2)
    if attraction_per_place <= 0:
        return None

    return {
        "hotel_per_night": hotel_per_night,
        "food_per_day": food_per_day,
        "transport_per_day": transport_per_day,
        "attraction_per_place": attraction_per_place,
        "source": source,
    }


def _get_exchange_rate(base_currency: str, target_currency: str) -> float:
    """Get exchange rate using public APIs, with graceful fallback."""
    base = base_currency.upper()
    target = target_currency.upper()
    if base == target:
        return 1.0

    # Primary: open.er-api provides wide currency coverage, including LKR.
    try:
        primary_url = f"https://open.er-api.com/v6/latest/{base}"
        response = requests.get(primary_url, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        rate = float(payload.get("rates", {}).get(target))
        if rate > 0:
            return rate
    except Exception:
        pass

    # Secondary fallback: Frankfurter for common currencies.
    try:
        response = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": base, "to": target},
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        rate = float(payload.get("rates", {}).get(target))
        if rate > 0:
            return rate
    except Exception:
        pass

    # Keep planner usable if conversion endpoints are unavailable.
    return 1.0

