"""
Weather MCP Server
Provides weather forecast data via the weather.gov API.
"""

import httpx
from geopy.geocoders import ArcGIS
from geopy.exc import GeocoderServiceError
from fastmcp import FastMCP

mcp = FastMCP("Weather Forecast")

WEATHER_API_BASE = "https://api.weather.gov"
HEADERS = {
    "User-Agent": "weather-mcp-server/1.0 (contact@example.com)",
    "Accept": "application/geo+json",
}


async def geocode_location(location: str) -> tuple[float, float]:
    """Convert a human-readable location to (latitude, longitude) using ArcGIS."""
    import asyncio
    geolocator = ArcGIS()
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, geolocator.geocode, location
        )
    except GeocoderServiceError as e:
        raise ValueError(f"Geocoding service error: {e}") from e
    if result is None:
        raise ValueError(f"Could not geocode location: '{location}'")
    return result.latitude, result.longitude


async def get_grid_point(lat: float, lon: float) -> dict:
    """Fetch NWS grid metadata for a lat/lon coordinate."""
    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        response = await client.get(
            f"{WEATHER_API_BASE}/points/{lat:.4f},{lon:.4f}",
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


async def get_forecast(forecast_url: str) -> dict:
    """Fetch the forecast from the NWS forecast URL."""
    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        response = await client.get(forecast_url, timeout=10)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_weather_forecast(location: str) -> str:
    """
    Get a multi-day weather forecast for any US city or location.

    Args:
        location: A US city/location string, e.g. "Ann Arbor, MI" or "Chicago, Illinois"

    Returns:
        A formatted multi-day forecast string.
    """
    # Step 1: Geocode
    try:
        lat, lon = await geocode_location(location)
    except (ValueError, httpx.HTTPError) as e:
        return f"Error geocoding '{location}': {e}"

    # Step 2: Get NWS grid point
    try:
        grid_data = await get_grid_point(lat, lon)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return (
                f"Location '{location}' (lat={lat:.4f}, lon={lon:.4f}) is outside "
                "NWS coverage. The weather.gov API only covers US locations."
            )
        return f"Error fetching grid point data: {e}"
    except httpx.HTTPError as e:
        return f"Error fetching grid point data: {e}"

    props = grid_data.get("properties", {})
    forecast_url = props.get("forecast")
    city = props.get("relativeLocation", {}).get("properties", {}).get("city", location)
    state = props.get("relativeLocation", {}).get("properties", {}).get("state", "")
    display_location = f"{city}, {state}" if state else city

    if not forecast_url:
        return "Error: Could not determine forecast URL from NWS grid point data."

    # Step 3: Fetch forecast
    try:
        forecast_data = await get_forecast(forecast_url)
    except httpx.HTTPError as e:
        return f"Error fetching forecast: {e}"

    periods = forecast_data.get("properties", {}).get("periods", [])
    if not periods:
        return "No forecast periods available."

    lines = [f"Weather forecast for {display_location}:\n"]
    for period in periods:
        name = period.get("name", "Unknown")
        temp = period.get("temperature", "?")
        temp_unit = period.get("temperatureUnit", "F")
        wind_speed = period.get("windSpeed", "")
        wind_dir = period.get("windDirection", "")
        short_forecast = period.get("shortForecast", "")
        detailed = period.get("detailedForecast", "")

        lines.append(f"## {name}")
        lines.append(f"  Temperature: {temp}°{temp_unit}")
        if wind_speed:
            lines.append(f"  Wind: {wind_dir} {wind_speed}")
        lines.append(f"  Conditions: {short_forecast}")
        if detailed:
            lines.append(f"  Details: {detailed}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
