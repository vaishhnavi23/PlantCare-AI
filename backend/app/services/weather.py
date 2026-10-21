"""Weather retrieval. OpenWeatherMap when OPENWEATHER_API_KEY is set, otherwise the keyless Open-Meteo API.
Nothing is invented: any failure raises WeatherError with a user-safe message."""
from __future__ import annotations

from datetime import datetime, timezone

import requests

TIMEOUT = 8
WMO = {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
       55: "Dense drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
       81: "Rain showers", 82: "Violent rain showers", 95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}


class WeatherError(RuntimeError):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def provider_name(api_key: str) -> str:
    return "OpenWeatherMap" if api_key else "Open-Meteo"


def _get(http, url, params):
    try:
        r = http.get(url, params=params, timeout=TIMEOUT)
    except requests.Timeout:
        raise WeatherError("The weather service took too long to respond. Please try again.", 504)
    except requests.RequestException:
        raise WeatherError("The weather service could not be reached. Check your internet connection and try again.", 502)
    if r.status_code == 401:
        raise WeatherError("The weather API key was rejected. Check OPENWEATHER_API_KEY.", 502)
    if r.status_code == 429:
        raise WeatherError("The weather service rate limit was reached. Try again later.", 429)
    if r.status_code != 200:
        raise WeatherError(f"The weather service returned an error ({r.status_code}).", 502)
    try:
        return r.json()
    except ValueError:
        raise WeatherError("The weather service returned an unreadable response.", 502)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _owm(location, key, http):
    geo = _get(http, "https://api.openweathermap.org/geo/1.0/direct", {"q": location, "limit": 1, "appid": key})
    if not geo:
        raise WeatherError("Location not found. Try a city name such as 'Davangere, IN'.", 404)
    g = geo[0]
    p = {"lat": g["lat"], "lon": g["lon"], "units": "metric", "appid": key}
    cur = _get(http, "https://api.openweathermap.org/data/2.5/weather", p)
    fc = _get(http, "https://api.openweathermap.org/data/2.5/forecast", p)
    rain = (cur.get("rain") or {}).get("1h")
    days: dict = {}
    for e in fc.get("list", []):
        d = days.setdefault(e["dt_txt"][:10], {"date": e["dt_txt"][:10], "min_c": 1e9, "max_c": -1e9, "precip_mm": 0.0, "conditions": None})
        d["min_c"], d["max_c"] = min(d["min_c"], e["main"]["temp_min"]), max(d["max_c"], e["main"]["temp_max"])
        d["precip_mm"] += (e.get("rain") or {}).get("3h", 0.0)
        d["conditions"] = d["conditions"] or (e["weather"][0]["description"].capitalize() if e.get("weather") else None)
    return {"provider": "OpenWeatherMap", "location": {"name": g.get("name"), "region": g.get("state"), "country": g.get("country"), "lat": g["lat"], "lon": g["lon"]},
            "observed_at": datetime.fromtimestamp(cur["dt"], timezone.utc).isoformat(timespec="seconds") if "dt" in cur else None, "fetched_at": _now(),
            "current": {"temperature_c": cur.get("main", {}).get("temp"), "humidity_pct": cur.get("main", {}).get("humidity"), "precipitation_mm": rain,
                        "conditions": cur["weather"][0]["description"].capitalize() if cur.get("weather") else None},
            "forecast": [{**d, "precip_mm": round(d["precip_mm"], 1)} for d in list(days.values())[:5]]}


def _meteo(location, http):
    geo = _get(http, "https://geocoding-api.open-meteo.com/v1/search", {"name": location.split(",")[0].strip(), "count": 1, "language": "en"})
    if not geo.get("results"):
        raise WeatherError("Location not found. Try a city name such as 'Davangere'.", 404)
    g = geo["results"][0]
    w = _get(http, "https://api.open-meteo.com/v1/forecast", {
        "latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto", "forecast_days": 5,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"})
    c, d = w.get("current") or {}, w.get("daily") or {}
    fc = [{"date": day, "min_c": d["temperature_2m_min"][i], "max_c": d["temperature_2m_max"][i], "precip_mm": d["precipitation_sum"][i],
           "conditions": WMO.get(d["weather_code"][i])} for i, day in enumerate(d.get("time", []))]
    return {"provider": "Open-Meteo", "location": {"name": g.get("name"), "region": g.get("admin1"), "country": g.get("country_code"), "lat": g["latitude"], "lon": g["longitude"]},
            "observed_at": c.get("time"), "fetched_at": _now(),
            "current": {"temperature_c": c.get("temperature_2m"), "humidity_pct": c.get("relative_humidity_2m"), "precipitation_mm": c.get("precipitation"),
                        "conditions": WMO.get(c.get("weather_code"))},
            "forecast": fc}


def fetch_weather(location: str, api_key: str = "", http=requests) -> dict:
    location = (location or "").strip()
    if len(location) < 2 or len(location) > 100:
        raise WeatherError("Please enter a location (2-100 characters).", 400)
    try:
        return _owm(location, api_key, http) if api_key else _meteo(location, http)
    except WeatherError:
        raise
    except (KeyError, IndexError, TypeError):
        raise WeatherError("The weather service returned incomplete data.", 502)
