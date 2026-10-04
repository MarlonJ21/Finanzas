from __future__ import annotations

import json
import sqlite3
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

from app.core.config import APP_DB_PATH
from app.services.db import query_one


def ensure_fx_db() -> None:
    APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(APP_DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS fx_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Default seeds if not present
        defaults = [
            ("mode", "auto"),
            ("manual_rate", "976.14"),
            ("cached_binance_rate", "976.00"),
            ("cached_at", "2000-01-01T00:00:00Z"),
        ]
        for k, v in defaults:
            con.execute(
                "INSERT OR IGNORE INTO fx_config (key, value, updated_at) VALUES (?, ?, ?)",
                [k, v, datetime.now(timezone.utc).isoformat()],
            )


def get_config_value(key: str, default: str = "") -> str:
    ensure_fx_db()
    with sqlite3.connect(APP_DB_PATH) as con:
        row = con.execute("SELECT value FROM fx_config WHERE key = ?", [key]).fetchone()
        return str(row[0]) if row else default


def set_config_value(key: str, value: str) -> None:
    ensure_fx_db()
    with sqlite3.connect(APP_DB_PATH) as con:
        now = datetime.now(timezone.utc).isoformat()
        con.execute(
            """
            INSERT INTO fx_config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            [key, value, now],
        )


def fetch_binance_p2p_rate() -> float | None:
    """Fetch real-time USDT/VES buy rate from Binance P2P public search API."""
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    payload = {
        "asset": "USDT",
        "fiat": "VES",
        "merchantCheck": False,
        "page": 1,
        "payTypes": [],
        "publisherType": None,
        "rows": 10,
        "tradeType": "BUY",
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            items = data.get("data", [])
            prices = [
                float(item["adv"]["price"])
                for item in items
                if isinstance(item, dict) and "adv" in item and "price" in item["adv"]
            ]
            if prices:
                # Return median of top 5 prices for stability against single outliers
                return round(float(statistics.median(prices[:5])), 2)
    except Exception:
        pass
    return None


def get_latest_bcv_rate() -> float:
    """Extract latest registered BCV rate from movements, fallback to standard."""
    try:
        bcv_res = query_one(
            """
            SELECT TasaRegistrada AS v FROM movimientos
            WHERE MonedaOriginal='VES' AND TasaRegistrada > 0 AND Cuenta IN ('BNC', 'Bancamiga', 'Efectivo')
            ORDER BY Fecha DESC, Hora DESC LIMIT 1
            """
        )
        val = float(bcv_res.get("v") or 0)
        if val > 0:
            return round(val, 2)
    except Exception:
        pass
    return 871.37


def get_fx_state(force_sync: bool = False) -> dict[str, Any]:
    """Get the current FX state with live or cached Binance rate and BCV rate."""
    ensure_fx_db()
    mode = get_config_value("mode", "auto")
    try:
        manual_rate = float(get_config_value("manual_rate", "976.14"))
    except ValueError:
        manual_rate = 976.14

    try:
        cached_rate = float(get_config_value("cached_binance_rate", "976.00"))
    except ValueError:
        cached_rate = 976.00

    cached_at_str = get_config_value("cached_at", "2000-01-01T00:00:00Z")
    try:
        cached_at = datetime.fromisoformat(cached_at_str.replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
    except Exception:
        age_seconds = 999999

    # Cache TTL is 15 minutes (900 seconds)
    ttl_seconds = 900
    live_rate: float | None = cached_rate

    if force_sync or (mode == "auto" and age_seconds > ttl_seconds):
        fetched = fetch_binance_p2p_rate()
        if fetched and fetched > 0:
            cached_rate = fetched
            live_rate = fetched
            now_iso = datetime.now(timezone.utc).isoformat()
            set_config_value("cached_binance_rate", str(fetched))
            set_config_value("cached_at", now_iso)
            cached_at_str = now_iso

    rate_bcv = get_latest_bcv_rate()
    rate_usdt = cached_rate if mode == "auto" else manual_rate
    spread_pct = round(((rate_usdt - rate_bcv) / rate_bcv) * 100, 2) if rate_bcv > 0 else 0.0

    return {
        "rate_bcv": rate_bcv,
        "rate_usdt": rate_usdt,
        "spread_pct": spread_pct,
        "mode": mode,
        "manual_rate": manual_rate,
        "live_rate": live_rate,
        "last_sync": cached_at_str,
        "source": "Binance P2P" if mode == "auto" else "Manual",
    }


def update_fx_settings(mode: str, manual_rate: float | None = None) -> dict[str, Any]:
    """Update FX mode and/or manual rate."""
    if mode in ("auto", "manual"):
        set_config_value("mode", mode)
    if manual_rate is not None and manual_rate > 0:
        set_config_value("manual_rate", str(round(manual_rate, 2)))
    return get_fx_state()
