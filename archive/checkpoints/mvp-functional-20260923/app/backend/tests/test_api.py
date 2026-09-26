from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import PROJECT_ROOT
from app.main import app
from app.services.etl import preview_import


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_data_status_reads_existing_outputs() -> None:
    response = client.get("/api/data/status")
    assert response.status_code == 200
    body = response.json()
    assert body["movement_count"] == 420
    assert body["planning_enabled"] is True


def test_dashboard_metric_parity() -> None:
    response = client.get("/api/dashboard/summary", params={"month": "2026-09", "scenario": "REALISTIC", "biweekly_period": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["personal_spend"] == 418.33
    assert body["monthly_budget"] == 631.21
    assert body["biweekly_spend"] == 415.76
    assert body["biweekly_budget"] == 315.58
    assert body["salary_collected_biweekly"] == 429.75


def test_planner_summary() -> None:
    response = client.get("/api/planner/summary", params={"scenario": "REALISTIC"})
    assert response.status_code == 200
    body = response.json()
    assert body["current_budget"] == 631.21
    assert body["forecast"] == 712.33
    assert body["suggested"] == 662.25
    assert body["final"] == 662.25


def test_movements_endpoint() -> None:
    response = client.get("/api/movements", params={"limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 5
    assert len(body["items"]) == 5


def test_invalid_rial_preview() -> None:
    files = {"file": ("bad.txt", b"not a csv", "text/plain")}
    response = client.post("/api/import/rial/preview", files=files)
    assert response.status_code == 200
    assert response.json()["validation_status"] == "FAIL"


def test_rial_preview_uses_existing_etl_without_commit() -> None:
    raw_file = PROJECT_ROOT / "raw" / "rial-movimientos_2000-01-01_a_2100-12-31.csv"
    output_file = PROJECT_ROOT / "output" / "movimientos.parquet"
    before_mtime = output_file.stat().st_mtime
    result = preview_import(raw_file, raw_file.name)
    after_mtime = output_file.stat().st_mtime
    assert result["validation_status"] == "PASS"
    assert result["transaction_rows"] == 420
    assert after_mtime == before_mtime
