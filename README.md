# Weather MCP Server

An MCP (Model Context Protocol) server that provides US weather forecasts using the [weather.gov API](https://www.weather.gov/documentation/services-web-api). Built with [FastMCP](https://gofastmcp.com) and Python.

## Features

- Get multi-day weather forecasts for any US city by name (e.g. "Ann Arbor, MI")
- Supports local stdio transport for use with Copilot CLI
- Supports HTTP transport for cloud hosting (Azure App Service, Railway, etc.)

## Tools

| Tool | Description |
|---|---|
| `get_weather_forecast` | Returns a multi-day forecast for a given US location string |

## Prerequisites

- Python 3.12+
- pip

## Local Setup

```bash
pip install -r requirements.txt
```

## Running Locally (stdio)

```bash
python server.py
```

This runs in stdio mode, suitable for use with GitHub Copilot CLI.

## Connecting to Copilot CLI

In a Copilot CLI session, run `/mcp add` and fill in the interactive form:

| Field | Value |
|---|---|
| Server Name | `weather` |
| Server Type | `2` (STDIO) |
| Command | `python C:/path/to/server.py` |
| Tools | `*` |

> **Tip:** Use forward slashes in the path to avoid them being stripped by the form.

Then ask naturally: *"What's the weather in Chicago, IL?"*

## Running as HTTP Server

Set the `TRANSPORT` environment variable to `streamable-http` before starting:

```bash
TRANSPORT=streamable-http PORT=8000 python server.py
```

The MCP endpoint will be available at `http://localhost:8000/mcp`.

## Deploying to Azure App Service

### 1. Create the App Service

```bash
az login
az group create --name weather-mcp-rg --location eastus
az webapp up --name <your-app-name> --resource-group weather-mcp-rg --runtime PYTHON:3.12 --sku F1
```

### 2. Set the transport environment variable

```bash
az webapp config appsettings set \
  --name <your-app-name> \
  --resource-group weather-mcp-rg \
  --settings TRANSPORT=streamable-http
```

### 3. Add GitHub Secrets

In your repo go to **Settings → Secrets → Actions** and add:

| Secret | Value |
|---|---|
| `AZURE_WEBAPP_NAME` | Your app name |
| `AZURE_WEBAPP_PUBLISH_PROFILE` | XML contents from Azure Portal → App Service → **Get publish profile** |

### 4. Push to main

The included GitHub Actions workflow (`.github/workflows/deploy.yml`) will automatically deploy on every push to `main`.

Your MCP endpoint will be live at:
```
https://<your-app-name>.azurewebsites.net/mcp
```

### Connecting Copilot CLI to the hosted server

Run `/mcp add` in a Copilot CLI session:

| Field | Value |
|---|---|
| Server Name | `weather` |
| Server Type | `3` (HTTP) |
| URL | `https://<your-app-name>.azurewebsites.net/mcp` |

## Project Structure

```
.
├── server.py                        # FastMCP server
├── requirements.txt                 # Python dependencies
├── startup.txt                      # Azure App Service startup command
├── assets/
│   └── weather_gov_openapi.json     # weather.gov OpenAPI spec (reference)
└── .github/
    └── workflows/
        └── deploy.yml               # Azure deployment workflow
```

## How It Works

1. **Geocode** — Converts the location string to lat/lon via the ArcGIS geocoder
2. **Grid lookup** — Calls `api.weather.gov/points/{lat},{lon}` to resolve the NWS forecast office and grid coordinates
3. **Forecast** — Fetches the full multi-day forecast from the NWS gridpoint forecast endpoint
