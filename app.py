"""FastAPI service for ChatGPT Statistics Dashboard.

Serves a Chart.js dashboard with cached analytics data
(1-hour TTL since data only changes on new OpenAI export).

Deployment: uvicorn app:app --host 127.0.0.1 --port 8203
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from analytics import build_dashboard_payload

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONVERSATIONS_PATH = Path(__file__).parent / "conversations.json"
TEMPLATE_PATH = Path(__file__).parent / "dashboard_template.html"
CACHE_TTL_SECONDS = 3600  # 1 hour

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ChatGPT Statistics Dashboard",
    root_path="/chatgpt_stats",
)

# ---------------------------------------------------------------------------
# Thread-safe cache
# ---------------------------------------------------------------------------
_cache_lock = threading.Lock()
_cache: dict[str, Any] = {
    "data": None,
    "built_at": 0.0,
}


def _get_cached_data(force_refresh: bool = False) -> dict[str, Any]:
    """Return cached dashboard data, rebuilding if stale or forced."""
    now = time.monotonic()
    with _cache_lock:
        if (
            not force_refresh
            and _cache["data"] is not None
            and (now - _cache["built_at"]) < CACHE_TTL_SECONDS
        ):
            return _cache["data"]

    data = build_dashboard_payload(str(CONVERSATIONS_PATH))

    with _cache_lock:
        _cache["data"] = data
        _cache["built_at"] = time.monotonic()

    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard_html():
    """Serve the dashboard HTML with injected data."""
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail="Template not found")

    data = _get_cached_data()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    data_json = json.dumps(data, ensure_ascii=False)
    data_json = data_json.replace("</", r"<\/")
    html = template.replace(
        "const DASHBOARD_DATA = {};",
        f"const DASHBOARD_DATA = {data_json};",
    )
    return HTMLResponse(content=html)


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
