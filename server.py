"""
Weather MCP Server
Provides weather forecast data via the weather.gov API.

Transport is controlled by the TRANSPORT environment variable:
  - "stdio" (default): for local use with Copilot CLI
  - "streamable-http": for cloud hosting (e.g. Azure App Service)

When using streamable-http, PORT env var sets the listening port (default 8000).
"""

import os
import sys
import logging
import httpx
from geopy.geocoders import ArcGIS
from geopy.exc import GeocoderServiceError
from fastmcp import FastMCP

# Configure logging to stdout immediately so Azure App Service captures all output.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

logger.info("Weather MCP Server: module loading...")

mcp = FastMCP("Weather Forecast")
logger.info("FastMCP instance created")

WEATHER_API_BASE = "https://api.weather.gov"
HEADERS = {
    "User-Agent": "weather-mcp-server/1.0 (contact@example.com)",
    "Accept": "application/geo+json",
}


async def geocode_location(location: str) -> tuple[float, float]:
    """Convert a human-readable location to (latitude, longitude) using ArcGIS."""
    import asyncio
    logger.info("Geocoding location: %s", location)
    geolocator = ArcGIS()
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, geolocator.geocode, location
        )
    except GeocoderServiceError as e:
        logger.error("Geocoding service error for '%s': %s", location, e)
        raise ValueError(f"Geocoding service error: {e}") from e
    if result is None:
        logger.warning("No geocoding result for '%s'", location)
        raise ValueError(f"Could not geocode location: '{location}'")
    logger.info("Geocoded '%s' -> lat=%.4f, lon=%.4f", location, result.latitude, result.longitude)
    return result.latitude, result.longitude


async def get_grid_point(lat: float, lon: float) -> dict:
    """Fetch NWS grid metadata for a lat/lon coordinate."""
    url = f"{WEATHER_API_BASE}/points/{lat:.4f},{lon:.4f}"
    logger.info("Fetching NWS grid point: %s", url)
    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        logger.info("Grid point response: %s", response.status_code)
        return response.json()


async def get_forecast(forecast_url: str) -> dict:
    """Fetch the forecast from the NWS forecast URL."""
    logger.info("Fetching forecast: %s", forecast_url)
    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        response = await client.get(forecast_url, timeout=10)
        response.raise_for_status()
        logger.info("Forecast response: %s", response.status_code)
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
    logger.info("get_weather_forecast called for: %s", location)

    # Step 1: Geocode
    try:
        lat, lon = await geocode_location(location)
    except (ValueError, httpx.HTTPError) as e:
        logger.error("Geocoding failed for '%s': %s", location, e)
        return f"Error geocoding '{location}': {e}"

    # Step 2: Get NWS grid point
    try:
        grid_data = await get_grid_point(lat, lon)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning("Location '%s' is outside NWS coverage (lat=%.4f, lon=%.4f)", location, lat, lon)
            return (
                f"Location '{location}' (lat={lat:.4f}, lon={lon:.4f}) is outside "
                "NWS coverage. The weather.gov API only covers US locations."
            )
        logger.error("HTTP error fetching grid point for '%s': %s", location, e)
        return f"Error fetching grid point data: {e}"
    except httpx.HTTPError as e:
        logger.error("HTTP error fetching grid point for '%s': %s", location, e)
        return f"Error fetching grid point data: {e}"

    props = grid_data.get("properties", {})
    forecast_url = props.get("forecast")
    city = props.get("relativeLocation", {}).get("properties", {}).get("city", location)
    state = props.get("relativeLocation", {}).get("properties", {}).get("state", "")
    display_location = f"{city}, {state}" if state else city

    if not forecast_url:
        logger.error("No forecast URL in grid point response for '%s'", location)
        return "Error: Could not determine forecast URL from NWS grid point data."

    # Step 3: Fetch forecast
    try:
        forecast_data = await get_forecast(forecast_url)
    except httpx.HTTPError as e:
        logger.error("HTTP error fetching forecast for '%s': %s", location, e)
        return f"Error fetching forecast: {e}"

    periods = forecast_data.get("properties", {}).get("periods", [])
    if not periods:
        return "No forecast periods available."

    logger.info("Returning forecast for '%s' (%d periods)", display_location, len(periods))
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


# Expose the ASGI app at module level so gunicorn can find it.
# This also validates the HTTP app builds successfully at import time.
_transport = os.environ.get("TRANSPORT", "stdio")
if _transport == "streamable-http":
    logger.info("Building HTTP ASGI app (transport=streamable-http)...")
    app = mcp.http_app(transport="streamable-http")
    logger.info("ASGI app ready")


if __name__ == "__main__":
    if _transport == "streamable-http":
        import uvicorn
        port = int(os.environ.get("PORT", 8000))
        logger.info("Starting uvicorn on 0.0.0.0:%d", port)
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True,
        )
    else:
        logger.info("Starting in stdio mode")
        mcp.run(transport="stdio")
