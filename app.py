"""FastAPI service for ChatGPT Statistics Dashboard.

Serves a Chart.js dashboard with cached analytics data.
See chatgpt-stats.service and CLAUDE.md for deployment details.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from analytics import build_dashboard_payload

logger = logging.getLogger(__name__)

CONVERSATIONS_PATH = Path(__file__).parent / "conversations.json"
CACHE_TTL_SECONDS = 3600  # 1 hour

app = FastAPI(
    title="ChatGPT Statistics Dashboard",
    root_path="/chatgpt_stats",
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {
    "data": None,
    "built_at": 0.0,
}


def _get_cached_data(force_refresh: bool = False) -> dict[str, Any]:
    """Return cached dashboard data, rebuilding if stale or forced.

    Holds the lock during rebuild to prevent concurrent requests from
    each parsing the full conversations.json independently.
    """
    with _cache_lock:
        now = time.monotonic()
        if (
            not force_refresh
            and _cache["data"] is not None
            and (now - _cache["built_at"]) < CACHE_TTL_SECONDS
        ):
            return _cache["data"]

        try:
            data = build_dashboard_payload(str(CONVERSATIONS_PATH))
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Data file not found: {CONVERSATIONS_PATH.name}. "
                    f"Download your ChatGPT export from OpenAI "
                    f"(Settings > Data Controls > Export) and place "
                    f"conversations.json in {CONVERSATIONS_PATH.parent}."
                ),
            )
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON in {CONVERSATIONS_PATH.name}: {e.msg} (line {e.lineno})",
            )

        _cache["data"] = data
        _cache["built_at"] = time.monotonic()
        return data


@app.get("/health")
@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    """Serve the overview dashboard page."""
    data = _get_cached_data()
    data_json = json.dumps(data, ensure_ascii=False).replace("</", r"<\/")
    return templates.TemplateResponse(
        "overview.html",
        {"request": request, "data_json": data_json, "page": "overview"},
    )



@app.get("/trends", response_class=HTMLResponse)
def trends(request: Request):
    """Serve the trends page."""
    data = _get_cached_data()
    data_json = json.dumps(data, ensure_ascii=False).replace("</", r"<\/")
    return templates.TemplateResponse(
        "trends.html",
        {"request": request, "data_json": data_json, "page": "trends"},
    )


@app.get("/patterns", response_class=HTMLResponse)
def patterns(request: Request):
    """Serve the patterns page."""
    data = _get_cached_data()
    data_json = json.dumps(data, ensure_ascii=False).replace("</", r"<\/")
    return templates.TemplateResponse(
        "patterns.html",
        {"request": request, "data_json": data_json, "page": "patterns"},
    )


@app.get("/api/data")
def api_data():
    """Return the full dashboard JSON payload."""
    return _get_cached_data()


@app.get("/api/refresh")
def api_refresh():
    """Force a cache rebuild and return fresh data."""
    data = _get_cached_data(force_refresh=True)
    return {
        "status": "refreshed",
        "generated_at": data["generated_at"],
    }
