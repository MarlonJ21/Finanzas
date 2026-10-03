from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import OUTPUT_DIR
from app.services.db import query_all, query_one


def as_float(value: Any) -> float:
    return round(float(value or 0), 2)


def as_pct(value: Any) -> float:
    return round(float(value or 0), 4)


def quality_summary() -> dict[str, Any]:
    path = OUTPUT_DIR / "calidad_datos.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_context() -> dict[str, Any]:
    return query_one(
        """
        SELECT
          CAST(MAX(FechaCorte) AS VARCHAR) AS cut_date,
          CAST(MAX(MesActual) AS VARCHAR) AS current_month,
          CAST(MAX(MesPlan) AS VARCHAR) AS plan_month,
          MAX(EstadoPlan) AS state
        FROM presupuesto
        """
    )


def sustainable_income(month: str | None = None) -> float:
    if month:
        like = f"{month[:7]}%" if not month.endswith("%") else month
        row = query_one(
            """
            SELECT SUM(MontoUSD) AS amount
            FROM movimientos
            WHERE Fecha LIKE ?
              AND Dominio='PERSONAL'
              AND (Categoria='Salario' OR (Categoria='Ingresos' AND Subcategoria='Salario'))
              AND EsIngresoEconomico=1
              AND Quincena=1
            """,
            [like],
        )
        amt = as_float(row.get("amount"))
        if amt > 0:
            return amt

    row = query_one(
        """
        SELECT MontoUSD AS amount
        FROM movimientos
        WHERE Dominio='PERSONAL'
          AND (Categoria='Salario' OR (Categoria='Ingresos' AND Subcategoria='Salario'))
          AND EsIngresoEconomico=1
          AND Quincena=1
        ORDER BY Fecha DESC
        LIMIT 1
        """
    )
    return as_float(row.get("amount"))


def month_bounds(month: str | None) -> tuple[str, str]:
    ctx = latest_context()
    month_value = month or str(ctx.get("current_month") or "")[:7]
    if len(month_value) >= 7:
        ym = month_value[:7]
    else:
        ym = str(ctx.get("current_month"))[:7]
    return f"{ym}-01", ym
