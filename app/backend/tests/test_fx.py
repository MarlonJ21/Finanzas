from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.fx import get_fx_state, update_fx_settings

client = TestClient(app)


def test_fx_state_structure() -> None:
    state = get_fx_state()
    assert "rate_bcv" in state
    assert "rate_usdt" in state
    assert "spread_pct" in state
    assert "mode" in state
    assert "manual_rate" in state
    assert state["rate_bcv"] > 0
    assert state["rate_usdt"] > 0


def test_fx_settings_update() -> None:
    # Set to manual with custom rate
    updated = update_fx_settings("manual", 999.50)
    assert updated["mode"] == "manual"
    assert updated["manual_rate"] == 999.50
    assert updated["rate_usdt"] == 999.50
    assert updated["source"] == "Manual"

    # Reset to auto
    auto_state = update_fx_settings("auto")
    assert auto_state["mode"] == "auto"
    assert auto_state["source"] == "Binance P2P"


def test_fx_api_endpoints() -> None:
    # GET /api/fx/rates
    res = client.get("/api/fx/rates")
    assert res.status_code == 200
    data = res.json()
    assert data["rate_bcv"] > 0
    assert data["rate_usdt"] > 0

    # POST /api/fx/config
    res_post = client.post("/api/fx/config", json={"mode": "manual", "manual_rate": 976.14})
    assert res_post.status_code == 200
    post_data = res_post.json()
    assert post_data["mode"] == "manual"
    assert post_data["manual_rate"] == 976.14
    assert post_data["rate_usdt"] == 976.14

    # Restore to auto
    client.post("/api/fx/config", json={"mode": "auto", "manual_rate": 976.14})

    # POST /api/fx/sync
    res_sync = client.post("/api/fx/sync")
    assert res_sync.status_code == 200
    sync_data = res_sync.json()
    assert sync_data["rate_usdt"] > 0
