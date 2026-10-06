from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.core.config import APP_VERSION, CONFIG_DIR, OUTPUT_DIR, PROJECT_ROOT
from app.services.classification import (
    CreateRulePayload,
    create_rule,
    delete_rule,
    get_classification_options,
    get_pending_classifications,
    get_rules,
)
from app.services.db import query_all, query_one
from app.services.etl import commit_import, preview_import, run_existing_pipeline
from app.services.fx import get_fx_state, update_fx_settings
from app.services.metrics import as_float, as_pct, latest_context, quality_summary, sustainable_income

router = APIRouter(prefix="/api")


class FxConfigPayload(BaseModel):
    mode: str = Field(pattern="^(auto|manual)$")
    manual_rate: float | None = Field(default=None, gt=0)


class OverridePayload(BaseModel):
    plan_month: str
    scenario: str
    manual_budget_usd: float = Field(ge=0)


def scenario_value(scenario: str | None) -> str:
    return (scenario or "REALISTIC").upper()


def month_like(month: str | None) -> str:
    if month:
        return f"{month[:7]}%"
    ctx = latest_context()
    return f"{str(ctx.get('current_month'))[:7]}%"


def current_quincena() -> int:
    cut = str(latest_context().get("cut_date") or "")
    try:
        return 1 if int(cut[-2:]) <= 15 else 2
    except Exception:
        return 1


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/data/status")
def data_status() -> dict[str, Any]:
    q = quality_summary()
    ctx = latest_context()
    totals = query_one(
        """
        SELECT
          SUM(CASE WHEN Escenario='REALISTIC' THEN MontoPresupuestadoUSD ELSE 0 END) AS current_budget_realistic,
          SUM(CASE WHEN Escenario='CURRENT' THEN PresupuestoSugeridoUSD ELSE 0 END) AS forecast_current,
          SUM(CASE WHEN Escenario='REALISTIC' THEN PresupuestoSugeridoUSD ELSE 0 END) AS forecast_realistic,
          SUM(CASE WHEN Escenario='AGGRESSIVE' THEN PresupuestoSugeridoUSD ELSE 0 END) AS forecast_aggressive
        FROM presupuesto
        """
    )
    movement_count = query_one("SELECT COUNT(*) AS n FROM movimientos").get("n", 0)
    output_files = list(OUTPUT_DIR.glob("*"))
    last_update = max((p.stat().st_mtime for p in output_files), default=None)
    return {
        "last_update": datetime.fromtimestamp(last_update, timezone.utc).isoformat() if last_update else None,
        "cut_date": ctx.get("cut_date"),
        "movement_count": movement_count,
        "current_month": ctx.get("current_month"),
        "plan_month": ctx.get("plan_month"),
        "planning_enabled": bool(ctx.get("plan_month")),
        "exact_duplicates": q.get("exact_duplicates", 0),
        "possible_duplicates": q.get("possible_duplicates", 0),
        "missing_fx": q.get("missing_fx", 0),
        "pending_classification": q.get("unclassified", 0),
        "current_budget_realistic": as_float(totals.get("current_budget_realistic")),
        "forecast_current": as_float(totals.get("forecast_current")),
        "forecast_realistic": as_float(totals.get("forecast_realistic")),
        "forecast_aggressive": as_float(totals.get("forecast_aggressive")),
    }


def prev_month_like(like_str: str) -> str:
    clean = like_str.replace("%", "").strip()[:7]
    try:
        y, m = int(clean[:4]), int(clean[5:7])
        if m == 1:
            return f"{y - 1:04d}-12%"
        return f"{y:04d}-{m - 1:02d}%"
    except Exception:
        return ""


@router.get("/dashboard/summary")
def dashboard_summary(
    month: str | None = None,
    scenario: str | None = "REALISTIC",
    biweekly_period: int | None = Query(default=None, ge=1, le=2),
) -> dict[str, Any]:
    sc = scenario_value(scenario)
    like = month_like(month)
    q = biweekly_period if isinstance(biweekly_period, int) else current_quincena()
    budget = query_one("SELECT SUM(MontoPresupuestadoUSD) AS v FROM presupuesto WHERE Escenario=?", [sc])
    spend = query_one(
        """
        SELECT SUM(MontoUSD) AS v FROM movimientos
        WHERE Fecha LIKE ? AND Dominio='PERSONAL' AND EsEgresoEconomico=1 AND EsPresupuestable=1
        """,
        [like],
    )
    salary = query_one(
        """
        SELECT SUM(MontoUSD) AS v FROM movimientos
        WHERE Fecha LIKE ? AND Dominio='PERSONAL' AND (Categoria='Salario' OR (Categoria='Ingresos' AND Subcategoria='Salario'))
          AND EsIngresoEconomico=1
        """,
        [like],
    )
    salary_q = query_one(
        """
        SELECT SUM(MontoUSD) AS v FROM movimientos
        WHERE Fecha LIKE ? AND Quincena=? AND Dominio='PERSONAL' AND (Categoria='Salario' OR (Categoria='Ingresos' AND Subcategoria='Salario'))
          AND EsIngresoEconomico=1
        """,
        [like, q],
    )
    bi_spend = query_one(
        """
        SELECT SUM(MontoUSD) AS v FROM movimientos
        WHERE Fecha LIKE ? AND Quincena=? AND Dominio='PERSONAL'
          AND EsEgresoEconomico=1 AND EsPresupuestable=1
        """,
        [like, q],
    )
    bi_budget = query_one(
        "SELECT SUM(MontoPresupuestoQuincenalUSD) AS v FROM presupuesto_quincenal WHERE Escenario=? AND Quincena=?",
        [sc, q],
    )
    income_sustainable = sustainable_income(month=like)
    monthly_budget = as_float(budget.get("v"))
    personal_spend = as_float(spend.get("v"))
    monthly_available = as_float(monthly_budget - personal_spend)
    biweekly_budget = as_float(bi_budget.get("v"))
    biweekly_spend = as_float(bi_spend.get("v"))
    biweekly_available = as_float(biweekly_budget - biweekly_spend)

    # Quincena Funding Logic:
    # Quincena 1 (days 1-15) is lived using the salary collected in Quincena 2 of the prior month.
    # Quincena 2 (days 16-31) is lived using the salary collected in Quincena 1 of current month.
    if q == 1:
        prev_like = prev_month_like(like)
        prev_salary = query_one(
            """
            SELECT SUM(MontoUSD) AS v FROM movimientos
            WHERE Fecha LIKE ? AND Quincena=2 AND Dominio='PERSONAL' AND (Categoria='Salario' OR (Categoria='Ingresos' AND Subcategoria='Salario'))
              AND EsIngresoEconomico=1
            """,
            [prev_like],
        )
        funding_val = as_float(prev_salary.get("v"))
        current_q_val = as_float(salary_q.get("v"))
        salary_funding = funding_val if funding_val > 0 else current_q_val
        if salary_funding == 0:
            salary_funding = as_float(income_sustainable / 2)
    else:
        current_q_val = as_float(salary_q.get("v"))
        salary_funding = current_q_val if current_q_val > 0 else as_float(income_sustainable / 2)

    # Safe to spend is strictly constrained by BOTH the quincena availability and remaining monthly budget
    safe_to_spend = as_float(max(min(monthly_available, biweekly_available), 0))
    saving_target = as_float(income_sustainable - monthly_budget)

    # Query latest registered FX rates from FX service
    fx_state = get_fx_state()
    rate_bcv = fx_state["rate_bcv"]
    rate_usdt = fx_state["rate_usdt"]

    return {
        "income_sustainable": income_sustainable,
        "salary_collected": as_float(salary.get("v")),
        "personal_spend": personal_spend,
        "monthly_budget": monthly_budget,
        "monthly_available": monthly_available,
        "monthly_consumed_pct": as_pct(personal_spend / monthly_budget if monthly_budget else 0),
        "biweekly_spend": biweekly_spend,
        "biweekly_budget": biweekly_budget,
        "biweekly_available": biweekly_available,
        "safe_to_spend": safe_to_spend,
        "saving_target": saving_target,
        "saving_rate": as_pct(saving_target / income_sustainable if income_sustainable else 0),
        "biweekly_period": q,
        "salary_collected_biweekly": salary_funding,
        "salary_deposited_this_period": as_float(salary_q.get("v")),
        "rate_bcv": rate_bcv,
        "rate_usdt": rate_usdt,
    }


@router.get("/dashboard/categories")
def dashboard_categories(month: str | None = None, scenario: str | None = "REALISTIC") -> list[dict[str, Any]]:
    sc = scenario_value(scenario)
    like = month_like(month)
    rows = query_all(
        """
        WITH spent AS (
          SELECT IdCategoria, SUM(MontoUSD) AS spent
          FROM movimientos
          WHERE Fecha LIKE ? AND Dominio='PERSONAL' AND EsEgresoEconomico=1 AND EsPresupuestable=1
          GROUP BY IdCategoria
        )
        SELECT
          p.Categoria AS category,
          p.Subcategoria AS subcategory,
          COALESCE(s.spent, 0) AS spent,
          p.MontoPresupuestadoUSD AS budget
        FROM presupuesto p
        LEFT JOIN spent s USING (IdCategoria)
        WHERE p.Escenario=?
        ORDER BY p.Categoria, p.Subcategoria
        """,
        [like, sc],
    )
    for row in rows:
        spent = as_float(row["spent"])
        budget = as_float(row["budget"])
        pct = spent / budget if budget else 0
        if budget == 0 and spent == 0:
            status = "NO_ACTIVITY"
        elif budget == 0:
            status = "NO_BUDGET"
        elif spent > budget:
            status = "EXCEEDED"
        elif pct >= 0.8:
            status = "NEAR_LIMIT"
        else:
            status = "WITHIN"
        row.update(
            {
                "spent": spent,
                "budget": budget,
                "available": as_float(budget - spent),
                "consumed_pct": as_pct(pct),
                "status": status,
            }
        )
    return rows


@router.get("/movements")
def movements(
    date_from: str | None = None,
    date_to: str | None = None,
    domain: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    account: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if date_from:
        where.append("Fecha >= ?")
        params.append(date_from)
    if date_to:
        where.append("Fecha <= ?")
        params.append(date_to)
    for col, value in [
        ("Dominio", domain),
        ("Categoria", category),
        ("Subcategoria", subcategory),
        ("Cuenta", account),
    ]:
        if value:
            where.append(f"{col} = ?")
            params.append(value)
    if search:
        where.append("lower(DescripcionOriginal) LIKE ?")
        params.append(f"%{search.lower()}%")
    clause = "WHERE " + " AND ".join(where) if where else ""
    total = query_one(f"SELECT COUNT(*) AS n FROM movimientos {clause}", params).get("n", 0)
    rows = query_all(
        f"""
        SELECT Fecha AS date, DescripcionOriginal AS description, Dominio AS domain,
               Categoria AS category, Subcategoria AS subcategory, Cuenta AS account,
               MontoUSD AS amount_usd, TipoRial AS type
        FROM movimientos
        {clause}
        ORDER BY Fecha DESC, Hora DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.get("/business/summary")
def business_summary(month: str | None = None) -> dict[str, Any]:
    months_rows = query_all(
        "SELECT DISTINCT strftime(TRY_CAST(Fecha AS DATE), '%Y-%m') as mes FROM movimientos WHERE Dominio='NEGOCIO' ORDER BY mes DESC"
    )
    available_months = [r["mes"] for r in months_rows if r.get("mes")]

    active_month = month
    if not active_month and available_months:
        active_month = available_months[0]
    elif active_month and active_month != "all":
        active_month = active_month[:7]

    where = ["Dominio='NEGOCIO'"]
    params: list[Any] = []
    if active_month and active_month != "all":
        where.append("Fecha LIKE ?")
        params.append(f"{active_month}%")
    where_str = " AND ".join(where)

    sales_row = query_one(
        f"SELECT SUM(MontoUSD) as total, COUNT(1) as count FROM movimientos WHERE {where_str} AND EsIngresoEconomico=1",
        params,
    )
    exp_row = query_one(
        f"SELECT SUM(MontoUSD) as total, COUNT(1) as count FROM movimientos WHERE {where_str} AND EsEgresoEconomico=1",
        params,
    )
    sales = as_float(sales_row.get("total"))
    sales_cnt = int(sales_row.get("count") or 0)
    exp = as_float(exp_row.get("total"))
    exp_cnt = int(exp_row.get("count") or 0)
    net_profit = as_float(sales - exp)
    margin = as_pct(net_profit / sales if sales else 0)
    avg_ticket = as_float(sales / sales_cnt if sales_cnt else 0)

    # Subcategory expenses
    exp_by_sub = query_all(
        f"""
        SELECT Subcategoria as subcategory, SUM(MontoUSD) as amount_usd, COUNT(1) as count
        FROM movimientos
        WHERE {where_str} AND EsEgresoEconomico=1
        GROUP BY Subcategoria
        ORDER BY amount_usd DESC
        """,
        params,
    )
    for r in exp_by_sub:
        amt = as_float(r["amount_usd"])
        r["amount_usd"] = amt
        r["pct"] = as_pct(amt / exp if exp else 0)
        r["count"] = int(r["count"])

    # Sales by account
    sales_by_acc = query_all(
        f"""
        SELECT Cuenta as account, SUM(MontoUSD) as amount_usd, COUNT(1) as count
        FROM movimientos
        WHERE {where_str} AND EsIngresoEconomico=1
        GROUP BY Cuenta
        ORDER BY amount_usd DESC
        """,
        params,
    )
    for r in sales_by_acc:
        amt = as_float(r["amount_usd"])
        r["amount_usd"] = amt
        r["pct"] = as_pct(amt / sales if sales else 0)
        r["count"] = int(r["count"])

    # Trend
    trend = query_all(
        """
        SELECT
          strftime(TRY_CAST(Fecha AS DATE), '%Y-%m') as month,
          ROUND(SUM(CASE WHEN EsIngresoEconomico=1 THEN MontoUSD ELSE 0 END), 2) as sales_usd,
          COUNT(CASE WHEN EsIngresoEconomico=1 THEN 1 END) as sales_count,
          ROUND(SUM(CASE WHEN EsEgresoEconomico=1 THEN MontoUSD ELSE 0 END), 2) as expenses_usd,
          COUNT(CASE WHEN EsEgresoEconomico=1 THEN 1 END) as expenses_count,
          ROUND(SUM(CASE WHEN EsIngresoEconomico=1 THEN MontoUSD ELSE 0 END) - SUM(CASE WHEN EsEgresoEconomico=1 THEN MontoUSD ELSE 0 END), 2) as net_profit_usd
        FROM movimientos
        WHERE Dominio='NEGOCIO'
        GROUP BY 1
        ORDER BY 1 DESC
        """
    )
    for t in trend:
        s = float(t["sales_usd"] or 0)
        p = float(t["net_profit_usd"] or 0)
        t["margin_pct"] = as_pct(p / s if s else 0)

    # All time
    all_time = query_one(
        """
        SELECT
          SUM(CASE WHEN EsIngresoEconomico=1 THEN MontoUSD ELSE 0 END) as sales,
          SUM(CASE WHEN EsEgresoEconomico=1 THEN MontoUSD ELSE 0 END) as expenses
        FROM movimientos
        WHERE Dominio='NEGOCIO'
        """
    )
    at_sales = as_float(all_time.get("sales"))
    at_exp = as_float(all_time.get("expenses"))

    return {
        "month": active_month,
        "total_sales_usd": sales,
        "sales_count": sales_cnt,
        "total_expenses_usd": exp,
        "expenses_count": exp_cnt,
        "net_profit_usd": net_profit,
        "profit_margin_pct": margin,
        "average_ticket_usd": avg_ticket,
        "all_time_sales_usd": at_sales,
        "all_time_expenses_usd": at_exp,
        "all_time_net_profit_usd": as_float(at_sales - at_exp),
        "expenses_by_subcategory": exp_by_sub,
        "sales_by_account": sales_by_acc,
        "monthly_trend": trend,
        "available_months": available_months,
    }


@router.get("/business/movements")
def business_movements(
    month: str | None = None,
    type: str | None = None,
    subcategory: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    where = ["Dominio='NEGOCIO'"]
    params: list[Any] = []
    if month and month != "all":
        where.append("Fecha LIKE ?")
        params.append(f"{month[:7]}%")
    if type and type.lower() in ("ingreso", "venta", "ventas"):
        where.append("EsIngresoEconomico=1")
    elif type and type.lower() in ("egreso", "gasto", "gastos"):
        where.append("EsEgresoEconomico=1")
    if subcategory:
        where.append("Subcategoria = ?")
        params.append(subcategory)
    if search:
        where.append("lower(DescripcionOriginal) LIKE ?")
        params.append(f"%{search.lower()}%")

    clause = "WHERE " + " AND ".join(where)
    total = query_one(f"SELECT COUNT(*) AS n FROM movimientos {clause}", params).get("n", 0)
    rows = query_all(
        f"""
        SELECT Fecha AS date, Hora AS time, DescripcionOriginal AS description, Dominio AS domain,
               Categoria AS category, Subcategoria AS subcategory, Cuenta AS account,
               MontoUSD AS amount_usd, MontoOriginal AS amount_original, MonedaOriginal AS currency_original,
               TipoRial AS type
        FROM movimientos
        {clause}
        ORDER BY Fecha DESC, Hora DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.get("/planner/summary")
def planner_summary(scenario: str | None = "REALISTIC", plan_month: str | None = None) -> dict[str, Any]:
    sc = scenario_value(scenario)
    row = query_one(
        """
        SELECT
          SUM(MontoPresupuestadoUSD) AS current_budget,
          SUM(ForecastProximoMes) AS forecast,
          SUM(PresupuestoSugeridoUSD) AS suggested,
          SUM(PresupuestoFinalUSD) AS final,
          MAX(MesPlan) AS plan_month,
          MAX(EstadoPlan) AS state,
          SUM(CASE WHEN ConfianzaPrediccion='HIGH' THEN 1 ELSE 0 END) AS confidence_high,
          SUM(CASE WHEN ConfianzaPrediccion='MEDIUM' THEN 1 ELSE 0 END) AS confidence_medium,
          SUM(CASE WHEN ConfianzaPrediccion='LOW' THEN 1 ELSE 0 END) AS confidence_low
        FROM presupuesto
        WHERE Escenario=? AND (? IS NULL OR CAST(MesPlan AS VARCHAR)=?)
        """,
        [sc, plan_month, plan_month],
    )
    income = sustainable_income(month=plan_month)
    final = as_float(row.get("final"))
    expected = as_float(income - final)
    return {
        "current_budget": as_float(row.get("current_budget")),
        "forecast": as_float(row.get("forecast")),
        "suggested": as_float(row.get("suggested")),
        "final": final,
        "expected_saving": expected,
        "expected_saving_pct": as_pct(expected / income if income else 0),
        "confidence_high": int(row.get("confidence_high") or 0),
        "confidence_medium": int(row.get("confidence_medium") or 0),
        "confidence_low": int(row.get("confidence_low") or 0),
        "planning_enabled": bool(row.get("plan_month")),
        "state": row.get("state"),
        "plan_month": row.get("plan_month"),
        "scenario": sc,
    }


@router.get("/planner/categories")
def planner_categories(scenario: str | None = "REALISTIC", plan_month: str | None = None) -> list[dict[str, Any]]:
    sc = scenario_value(scenario)
    return query_all(
        """
        SELECT
          IdCategoria AS id_category, Dominio AS domain, Categoria AS category, Subcategoria AS subcategory,
          TipoForecast AS forecast_type, ConfianzaPrediccion AS confidence, ConfidenceScore AS confidence_score,
          Flexibilidad AS flexibility, EsEsencial AS is_essential,
          MontoPresupuestadoUSD AS current_budget, GastoActualMTD AS current_mtd,
          GastoAnteriorMismoPeriodo AS previous_same_period, ProyeccionCierreMesActual AS projected_close,
          ForecastProximoMes AS forecast_next_month, PresupuestoSugeridoUSD AS suggested_budget,
          PresupuestoManualUSD AS manual_budget, PresupuestoFinalUSD AS final_budget,
          FactorEscenario AS scenario_factor
        FROM presupuesto
        WHERE Escenario=? AND (? IS NULL OR CAST(MesPlan AS VARCHAR)=?)
        ORDER BY Categoria, Subcategoria
        """,
        [sc, plan_month, plan_month],
    )


@router.get("/planner/categories/{id_category}")
def planner_category_detail(id_category: str, scenario: str | None = "REALISTIC") -> dict[str, Any]:
    sc = scenario_value(scenario)
    row = query_one(
        """
        SELECT
          IdCategoria AS id_category, Dominio AS domain, Categoria AS category, Subcategoria AS subcategory,
          PromedioHistorico AS historical_average, MedianaHistorica AS historical_median,
          GastoActualMTD AS current_mtd, GastoAnteriorMismoPeriodo AS previous_same_period,
          GastoMesAnteriorCompleto AS previous_full_month, ProyeccionCierreMesActual AS projected_close,
          ForecastProximoMes AS forecast_next_month, TipoForecast AS forecast_type,
          MetodoPrediccion AS method, ConfianzaPrediccion AS confidence, ConfidenceScore AS confidence_score,
          ConfidenceReason AS confidence_reason, Escenario AS scenario, FactorEscenario AS scenario_factor,
          PresupuestoSugeridoUSD AS suggested_budget, PresupuestoManualUSD AS manual_budget, PresupuestoFinalUSD AS final_budget,
          PresupuestoSugeridoUSD AS suggested, PresupuestoManualUSD AS manual, PresupuestoFinalUSD AS final,
          Flexibilidad AS flexibility, EsEsencial AS is_essential, FloorUSD AS floor_usd, CapUSD AS cap_usd
        FROM presupuesto
        WHERE IdCategoria=? AND Escenario=?
        LIMIT 1
        """,
        [id_category, sc],
    )
    if not row:
        raise HTTPException(status_code=404, detail="CATEGORY_NOT_FOUND")
    return row


def rewrite_override(payload: OverridePayload, id_category: str) -> None:
    path = CONFIG_DIR / "budget_next_month_overrides.csv"
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    fields = ["MesPlan", "Escenario", "IdCategoria", "PresupuestoManualUSD"]
    rows = [
        row
        for row in rows
        if not (
            row.get("MesPlan") == payload.plan_month
            and row.get("Escenario") == scenario_value(payload.scenario)
            and row.get("IdCategoria") == id_category
        )
    ]
    rows.append(
        {
            "MesPlan": payload.plan_month,
            "Escenario": scenario_value(payload.scenario),
            "IdCategoria": id_category,
            "PresupuestoManualUSD": f"{payload.manual_budget_usd:.2f}",
        }
    )
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@router.put("/planner/overrides/{id_category}")
def put_override(id_category: str, payload: OverridePayload) -> dict[str, Any]:
    if not query_one("SELECT IdCategoria FROM presupuesto WHERE IdCategoria=? LIMIT 1", [id_category]):
        raise HTTPException(status_code=404, detail="CATEGORY_NOT_FOUND")
    rewrite_override(payload, id_category)
    result = run_existing_pipeline(PROJECT_ROOT)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail={"error": "ETL_FAILED", "stderr": result.stderr[-2000:]})
    return {
        "status": "PASS",
        "etl_stdout": result.stdout[-2000:],
        "category": planner_category_detail(id_category, payload.scenario),
    }


async def save_upload(upload: UploadFile) -> Path:
    suffix = ".csv"
    tmp_dir = Path(tempfile.mkdtemp(prefix="rial_upload_"))
    target = tmp_dir / f"upload{suffix}"
    with target.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return target


@router.post("/import/rial/preview")
async def rial_preview(file: UploadFile = File(...)) -> dict[str, Any]:
    path = await save_upload(file)
    try:
        return preview_import(path, file.filename or "upload.csv")
    except Exception as exc:
        return {
            "filename": file.filename,
            "validation_status": "FAIL",
            "errors": [str(exc)],
            "warnings": [],
        }


@router.post("/import/rial/commit")
async def rial_commit(file: UploadFile = File(...), force: bool = False) -> dict[str, Any]:
    path = await save_upload(file)
    try:
        return commit_import(path, file.filename or "upload.csv", force=force)
    except Exception as exc:
        return {"filename": file.filename, "commit_status": "FAIL", "errors": [str(exc)], "rollback": True}


@router.get("/classification/pending")
def classification_pending() -> dict[str, Any]:
    return get_pending_classifications()


@router.get("/classification/rules")
def classification_rules() -> dict[str, Any]:
    return get_rules()


@router.get("/classification/options")
def classification_options() -> dict[str, Any]:
    return get_classification_options()


@router.post("/classification/rules")
def classification_create_rule(payload: CreateRulePayload) -> dict[str, Any]:
    try:
        return create_rule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error creando regla: {str(exc)}")


@router.delete("/classification/rules/{rule_id}")
def classification_delete_rule(rule_id: str) -> dict[str, Any]:
    try:
        return delete_rule(rule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error eliminando regla: {str(exc)}")


@router.get("/fx/rates")
def fx_rates() -> dict[str, Any]:
    return get_fx_state()


@router.post("/fx/config")
def fx_config(payload: FxConfigPayload) -> dict[str, Any]:
    return update_fx_settings(payload.mode, payload.manual_rate)


@router.post("/fx/sync")
def fx_sync() -> dict[str, Any]:
    return get_fx_state(force_sync=True)


