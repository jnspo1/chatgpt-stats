"""Tests for the FastAPI app (app.py) routes and caching behaviour."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException


# ── HTML page routes ──────────────────────────


class TestOverviewPage:
    def test_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_content_type_is_html(self, client):
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_contains_page_title(self, client):
        response = client.get("/")
        assert "ChatGPT Statistics" in response.text

    def test_contains_overview_title(self, client):
        response = client.get("/")
        assert "Overview" in response.text

    def test_contains_dashboard_data_script(self, client):
        """The template injects the payload as DASHBOARD_DATA in a script."""
        response = client.get("/")
        assert "DASHBOARD_DATA" in response.text

    def test_data_json_contains_summary(self, client):
        """The injected JSON should include the summary section."""
        response = client.get("/")
        assert '"total_conversations"' in response.text


class TestTrendsPage:
    def test_returns_200(self, client):
        response = client.get("/trends")
        assert response.status_code == 200

    def test_content_type_is_html(self, client):
        response = client.get("/trends")
        assert "text/html" in response.headers["content-type"]

    def test_contains_page_title(self, client):
        response = client.get("/trends")
        assert "Trends" in response.text

    def test_contains_chatgpt_statistics(self, client):
        response = client.get("/trends")
        assert "ChatGPT Statistics" in response.text


class TestPatternsPage:
    def test_returns_200(self, client):
        response = client.get("/patterns")
        assert response.status_code == 200

    def test_content_type_is_html(self, client):
        response = client.get("/patterns")
        assert "text/html" in response.headers["content-type"]

    def test_contains_page_title(self, client):
        response = client.get("/patterns")
        assert "Patterns" in response.text

    def test_contains_chatgpt_statistics(self, client):
        response = client.get("/patterns")
        assert "ChatGPT Statistics" in response.text


# ── JSON API routes ───────────────────────────


class TestApiData:
    def test_returns_200(self, client):
        response = client.get("/api/data")
        assert response.status_code == 200

    def test_content_type_is_json(self, client):
        response = client.get("/api/data")
        assert "application/json" in response.headers["content-type"]

    def test_payload_has_summary(self, client):
        data = client.get("/api/data").json()
        assert "summary" in data

    def test_payload_has_generated_at(self, client):
        data = client.get("/api/data").json()
        assert "generated_at" in data

    def test_summary_has_expected_keys(self, client, mock_payload):
        data = client.get("/api/data").json()
        summary = data["summary"]
        expected_keys = {
            "total_conversations",
            "total_messages",
            "date_range",
            "daily_avg_conversations",
            "daily_avg_messages",
            "avg_messages_per_conversation",
            "total_words",
            "total_code_blocks",
            "avg_words_per_message",
            "code_block_percentage",
        }
        assert expected_keys.issubset(summary.keys())

    def test_payload_has_chart_sections(self, client):
        data = client.get("/api/data").json()
        for key in ("chart", "monthly", "weekly", "hourly"):
            assert key in data, f"Missing key: {key}"

    def test_payload_has_content_sections(self, client):
        data = client.get("/api/data").json()
        for key in ("content_chart", "content_monthly", "content_weekly"):
            assert key in data, f"Missing key: {key}"

    def test_payload_has_analysis_sections(self, client):
        data = client.get("/api/data").json()
        for key in ("gap_analysis", "activity_by_year", "period_comparison"):
            assert key in data, f"Missing key: {key}"

    def test_payload_matches_mock(self, client, mock_payload):
        """The API should return exactly the mocked payload."""
        data = client.get("/api/data").json()
        assert data == mock_payload


class TestApiRefresh:
    def test_returns_200(self, client):
        response = client.get("/api/refresh")
        assert response.status_code == 200

    def test_content_type_is_json(self, client):
        response = client.get("/api/refresh")
        assert "application/json" in response.headers["content-type"]

    def test_response_has_status_refreshed(self, client):
        data = client.get("/api/refresh").json()
        assert data["status"] == "refreshed"

    def test_response_has_generated_at(self, client):
        data = client.get("/api/refresh").json()
        assert "generated_at" in data


# ── Health check ──────────────────────────────


class TestHealthCheck:
    def test_healthz_returns_200(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200


# ── Error handling ────────────────────────────


class TestMissingDataFile:
    def test_overview_503_when_data_missing(self, client):
        """When conversations.json is missing, pages should return 503."""
        with patch(
            "app._get_cached_data",
            side_effect=HTTPException(status_code=503, detail="Data file not found"),
        ):
            response = client.get("/")
            assert response.status_code == 503

    def test_api_data_503_when_data_missing(self, client):
        with patch(
            "app._get_cached_data",
            side_effect=HTTPException(status_code=503, detail="Data file not found"),
        ):
            response = client.get("/api/data")
            assert response.status_code == 503

    def test_trends_503_when_data_missing(self, client):
        with patch(
            "app._get_cached_data",
            side_effect=HTTPException(status_code=503, detail="Data file not found"),
        ):
            response = client.get("/trends")
            assert response.status_code == 503

    def test_patterns_503_when_data_missing(self, client):
        with patch(
            "app._get_cached_data",
            side_effect=HTTPException(status_code=503, detail="Data file not found"),
        ):
            response = client.get("/patterns")
            assert response.status_code == 503


class TestInvalidJsonFile:
    def test_api_data_500_when_json_invalid(self, client):
        """When conversations.json has bad JSON, the API should return 500."""
        with patch(
            "app._get_cached_data",
            side_effect=HTTPException(
                status_code=500, detail="Invalid JSON in conversations.json"
            ),
        ):
            response = client.get("/api/data")
            assert response.status_code == 500


# ── Caching behaviour ────────────────────────


class TestCaching:
    def test_second_request_uses_cache(self, client):
        """After first call populates cache, build_dashboard_payload is
        called only once for two requests."""
        with patch("app.build_dashboard_payload") as mock_build:
            mock_build.return_value = {
                "generated_at": "2024-01-15T12:00:00",
                "summary": {},
            }
            # Reset cache to force a build on first call
            import app as app_module

            app_module._cache["data"] = None
            app_module._cache["built_at"] = 0.0

            client.get("/api/data")
            client.get("/api/data")
            assert mock_build.call_count == 1

    def test_refresh_forces_rebuild(self, client):
        """The /api/refresh endpoint should call build_dashboard_payload
        even when the cache is fresh."""
        with patch("app.build_dashboard_payload") as mock_build:
            mock_build.return_value = {
                "generated_at": "2024-01-15T12:00:00",
                "summary": {},
            }
            import app as app_module

            app_module._cache["data"] = None
            app_module._cache["built_at"] = 0.0

            # First call populates cache
            client.get("/api/data")
            assert mock_build.call_count == 1

            # Refresh should rebuild despite fresh cache
            client.get("/api/refresh")
            assert mock_build.call_count == 2


# ── 404 for unknown routes ───────────────────


class TestNotFound:
    def test_unknown_route_returns_404(self, client):
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_unknown_api_route_returns_404(self, client):
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
