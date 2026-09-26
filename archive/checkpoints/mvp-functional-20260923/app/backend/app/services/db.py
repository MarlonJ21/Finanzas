from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from app.core.config import OUTPUT_DIR


def parquet_path(name: str) -> str:
    return str((OUTPUT_DIR / name).resolve()).replace("\\", "/")


def duckdb_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class AnalyticsDB:
    def __init__(self) -> None:
        self.con = duckdb.connect(database=":memory:", read_only=False)
        self._register()

    def _register(self) -> None:
        files = {
            "movimientos": "movimientos.parquet",
            "categorias": "categorias.parquet",
            "dim_fecha": "dim_fecha.parquet",
            "presupuesto": "presupuesto.parquet",
            "presupuesto_quincenal": "presupuesto_quincenal.parquet",
        }
        for view, filename in files.items():
            path = OUTPUT_DIR / filename
            if path.exists():
                source = duckdb_string(parquet_path(filename))
                self.con.execute(
                    f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM read_parquet({source})"
                )

    def one(self, sql: str, params: list[Any] | None = None) -> dict[str, Any]:
        cur = self.con.execute(sql, params or [])
        row = cur.fetchone()
        if row is None:
            return {}
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

    def all(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cur = self.con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self.con.close()


def query_one(sql: str, params: list[Any] | None = None) -> dict[str, Any]:
    db = AnalyticsDB()
    try:
        return db.one(sql, params)
    finally:
        db.close()


def query_all(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    db = AnalyticsDB()
    try:
        return db.all(sql, params)
    finally:
        db.close()


def output_mtime(path: Path) -> float | None:
    return path.stat().st_mtime if path.exists() else None
