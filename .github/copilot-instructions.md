# Copilot Instructions

## Project Overview

This is a single-file Python MCP (Model Context Protocol) server built with [FastMCP](https://gofastmcp.com). It exposes one tool — `get_weather_forecast` — that returns multi-day US weather forecasts by resolving a location string through a 3-step pipeline:

1. **Geocode** — ArcGIS geocoder (`geopy`) converts a city/location string to lat/lon
2. **Grid lookup** — `api.weather.gov/points/{lat},{lon}` resolves the NWS forecast office and grid coordinates
3. **Forecast fetch** — The NWS gridpoint forecast URL from step 2 returns the full multi-day forecast

All of this lives in `server.py`. There are no modules, packages, or subdirectories with code.

## Setup

```bash
pip install -r requirements.txt   # fastmcp, httpx, geopy, uvicorn
```

## Running

```bash
# stdio mode (local / Copilot CLI integration)
python server.py

# HTTP mode (cloud hosting)
TRANSPORT=streamable-http PORT=8000 python server.py
# MCP endpoint: http://localhost:8000/mcp
```

The `TRANSPORT` env var controls the mode; it defaults to `stdio`.

## Transport Modes

- **stdio** — for local use; connect via Copilot CLI `/mcp add` using `Server Type: 2 (STDIO)`
- **streamable-http** — for cloud deployment (Azure App Service, Railway, etc.); connect via `/mcp add` using `Server Type: 3 (HTTP)` pointing at `https://<app>.azurewebsites.net/mcp`

`startup.txt` (`python server.py`) is the Azure App Service startup command — do not change the filename, Azure reads it directly.

## Deployment

Push to `main` triggers `.github/workflows/deploy.yml`, which deploys to Azure App Service. Two GitHub secrets are required:

- `AZURE_WEBAPP_NAME` — the Azure app name
- `AZURE_WEBAPP_PUBLISH_PROFILE` — XML publish profile from Azure Portal

## Key Implementation Notes

- `httpx` calls use `verify=False` (SSL verification disabled) — intentional for the weather.gov API environment.
- The NWS API only covers US locations; non-US coordinates return a 404, which is handled explicitly with a descriptive error message.
- `assets/weather_gov_openapi.json` is a reference copy of the weather.gov OpenAPI spec — not loaded at runtime.
- The tool returns plain formatted strings (not structured data), since MCP tools surface output directly to the AI.
