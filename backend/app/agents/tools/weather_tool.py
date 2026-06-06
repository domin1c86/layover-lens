from __future__ import annotations

from datetime import date

import httpx

from app.config import settings
from app.agents.tools.types import AgentToolResult


class WeatherForecastTool:
    name = "weather_forecast"
    description = "Return current or daily weather forecast for a city and optional ISO travel date."
    input_schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name to geocode"},
            "travel_date": {"type": "string", "description": "Optional ISO date such as 2026-06-05"},
            "language": {"type": "string", "description": "zh or en"},
        },
        "required": ["city"],
    }

    def run(self, arguments: dict) -> AgentToolResult:
        city = str(arguments.get("city") or "").strip()
        language = str(arguments.get("language") or "zh")
        travel_date = str(arguments.get("travel_date") or "").strip()
        if not city:
            return self._error("Weather lookup needs a city.", {"reason": "missing_city"})
        if settings.ai_agent_weather_provider != "open_meteo":
            return self._error("Weather provider is not available.", {"provider": settings.ai_agent_weather_provider})
        try:
            place = self._geocode(city, language)
            if not place:
                return self._error(f"Unable to find weather location for {city}.", {"city": city})
            forecast = self._forecast(place, travel_date)
        except httpx.HTTPError as exc:
            return self._error("Weather service request failed.", {"error": str(exc)[:200]})
        return AgentToolResult(
            name=self.name,
            status="success",
            content=forecast["summary"],
            data=forecast,
        )

    def _geocode(self, city: str, language: str) -> dict | None:
        response = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": city,
                "count": 1,
                "language": "zh" if language == "zh" else "en",
                "format": "json",
            },
            timeout=settings.ai_agent_weather_timeout_seconds,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        return results[0] if results else None

    def _forecast(self, place: dict, travel_date: str) -> dict:
        params = {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "timezone": "auto",
            "forecast_days": 16,
        }
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=settings.ai_agent_weather_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        city_name = place.get("name") or ""
        country = place.get("country") or ""
        current = payload.get("current") or {}
        daily = payload.get("daily") or {}
        target_date = _safe_iso_date(travel_date)
        selected_daily = _select_daily(daily, target_date)
        if selected_daily:
            summary = (
                f"Weather for {city_name}, {country} on {selected_daily['date']}: "
                f"{selected_daily['min_temp']} C to {selected_daily['max_temp']} C, "
                f"precipitation probability {selected_daily['precipitation_probability']}%."
            )
        else:
            summary = (
                f"Current weather for {city_name}, {country}: "
                f"{current.get('temperature_2m')} C, wind {current.get('wind_speed_10m')} km/h."
            )
        return {
            "provider": "open_meteo",
            "city": city_name,
            "country": country,
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
            "current": current,
            "daily": selected_daily,
            "summary": summary,
        }

    def _error(self, content: str, data: dict) -> AgentToolResult:
        return AgentToolResult(name=self.name, status="error", content=content, data=data)


def _safe_iso_date(value: str) -> str:
    if not value:
        return ""
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return ""


def _select_daily(daily: dict, target_date: str) -> dict | None:
    dates = daily.get("time") or []
    if not dates:
        return None
    index = dates.index(target_date) if target_date in dates else 0
    return {
        "date": dates[index],
        "max_temp": _at(daily.get("temperature_2m_max"), index),
        "min_temp": _at(daily.get("temperature_2m_min"), index),
        "precipitation_probability": _at(daily.get("precipitation_probability_max"), index),
        "weather_code": _at(daily.get("weather_code"), index),
    }


def _at(values, index: int):
    return values[index] if isinstance(values, list) and index < len(values) else None
