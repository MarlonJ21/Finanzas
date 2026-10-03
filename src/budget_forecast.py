import calendar
import os
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


SCENARIOS = ["CURRENT", "REALISTIC", "AGGRESSIVE"]
PLAN_STATUS = "DRAFT"
SHRINKAGE_K_DAYS = 10

NEW_FACT_COLUMNS = [
    "MesActual",
    "MesPlan",
    "FechaCorte",
    "EstadoPlan",
    "GastoActualMTD",
    "GastoAnteriorMismoPeriodo",
    "GastoMesAnteriorCompleto",
    "PromedioHistorico",
    "MedianaHistorica",
    "VariacionMismoPeriodoPct",
    "ProyeccionCierreMesActual",
    "ForecastProximoMes",
    "MetodoPrediccion",
    "ConfianzaPrediccion",
    "TipoForecast",
    "PresupuestoSugeridoUSD",
    "PresupuestoManualUSD",
    "PresupuestoFinalUSD",
    "FactorEscenario",
    "Flexibilidad",
    "EsEsencial",
    "ConfidenceScore",
    "ConfidenceReason",
    "PresupuestoBaseForecastUSD",
    "AjusteEscenarioUSD",
    "FloorUSD",
    "CapUSD",
]

FORECAST_RULE_COLUMNS = [
    "IdCategoria",
    "TipoForecastOverride",
    "Flexibilidad",
    "EsEsencial",
    "FactorRealistic",
    "FactorAggressive",
    "FloorUSD",
    "CapUSD",
    "Notas",
]

FLEXIBILITY_FACTORS = {
    "NONE": (1.00, 1.00),
    "LOW": (0.95, 0.90),
    "MEDIUM": (0.90, 0.80),
    "HIGH": (0.80, 0.60),
}


@dataclass
class ForecastContext:
    planning_enabled: bool
    current_month: pd.Timestamp
    plan_month: pd.Timestamp
    cut_date: pd.Timestamp
    elapsed_days: int
    days_in_month: int


def _first_day(ts: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(year=ts.year, month=ts.month, day=1)


def _next_month(ts: pd.Timestamp) -> pd.Timestamp:
    return _first_day(ts + pd.DateOffset(months=1))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    if den is None or abs(float(den)) < 1e-9:
        return default
    return float(num) / float(den)


def _round_money(value: float) -> float:
    if pd.isna(value) or value < 0:
        return 0.0
    return round(float(value), 2)


def _ensure_override_file(config_dir: str) -> str:
    path = os.path.join(config_dir, "budget_next_month_overrides.csv")
    if not os.path.exists(path):
        pd.DataFrame(columns=["MesPlan", "Escenario", "IdCategoria", "PresupuestoManualUSD"]).to_csv(
            path, index=False, encoding="utf-8-sig"
        )
    return path


def _load_forecast_rules(config_dir: str) -> pd.DataFrame:
    path = os.path.join(config_dir, "budget_forecast_rules.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=FORECAST_RULE_COLUMNS)

    rules = pd.read_csv(path)
    for col in FORECAST_RULE_COLUMNS:
        if col not in rules.columns:
            rules[col] = np.nan

    rules["IdCategoria"] = rules["IdCategoria"].astype(str)
    rules["TipoForecastOverride"] = rules["TipoForecastOverride"].fillna("").astype(str).str.strip().str.upper()
    rules["Flexibilidad"] = rules["Flexibilidad"].fillna("MEDIUM").astype(str).str.strip().str.upper()
    rules.loc[~rules["Flexibilidad"].isin(FLEXIBILITY_FACTORS), "Flexibilidad"] = "MEDIUM"
    rules["EsEsencial"] = pd.to_numeric(rules["EsEsencial"], errors="coerce").fillna(0).astype(int)
    rules["FactorRealistic"] = pd.to_numeric(rules["FactorRealistic"], errors="coerce")
    rules["FactorAggressive"] = pd.to_numeric(rules["FactorAggressive"], errors="coerce")
    rules["FloorUSD"] = pd.to_numeric(rules["FloorUSD"], errors="coerce").fillna(0.0)
    rules["CapUSD"] = pd.to_numeric(rules["CapUSD"], errors="coerce")
    return rules[FORECAST_RULE_COLUMNS]


def _planning_context(df_mov: pd.DataFrame) -> ForecastContext:
    dates = pd.to_datetime(df_mov["Fecha"], errors="coerce")
    cut_date = dates.max().normalize()
    current_month = _first_day(cut_date)
    plan_month = _next_month(current_month)
    days_in_month = calendar.monthrange(current_month.year, current_month.month)[1]
    elapsed_days = min(cut_date.day, days_in_month)

    month_mask = (dates >= current_month) & (dates <= cut_date)
    salary_q1 = df_mov[
        month_mask
        & (df_mov["Dominio"] == "PERSONAL")
        & ((df_mov["Categoria"] == "Salario") | ((df_mov["Categoria"] == "Ingresos") & (df_mov["Subcategoria"] == "Salario")))
        & (df_mov["EsIngresoEconomico"] == 1)
        & (df_mov["Quincena"] == 1)
        & (df_mov["MontoUSD"] > 0)
    ]

    return ForecastContext(
        planning_enabled=not salary_q1.empty,
        current_month=current_month,
        plan_month=plan_month,
        cut_date=cut_date,
        elapsed_days=elapsed_days,
        days_in_month=days_in_month,
    )


def _monthly_matrix(df_mov: pd.DataFrame, id_categories: pd.Index, ctx: ForecastContext) -> pd.DataFrame:
    df = df_mov[
        (df_mov["Dominio"] == "PERSONAL")
        & (df_mov["EsEgresoEconomico"] == 1)
        & (df_mov["EsPresupuestable"] == 1)
    ].copy()
    df["FechaDt"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Mes"] = df["FechaDt"].values.astype("datetime64[M]")
    hist = df[df["FechaDt"] < ctx.current_month].copy()

    if hist.empty:
        return pd.DataFrame(index=id_categories)

    months = pd.period_range(hist["Mes"].min(), ctx.current_month - pd.DateOffset(months=1), freq="M").to_timestamp()
    grouped = hist.groupby(["IdCategoria", "Mes"])["MontoUSD"].sum().unstack(fill_value=0.0)
    grouped = grouped.reindex(index=id_categories, columns=months, fill_value=0.0)
    return grouped


def _sum_between(df_mov: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, id_categories: pd.Index) -> pd.Series:
    dates = pd.to_datetime(df_mov["Fecha"], errors="coerce")
    df = df_mov[
        (dates >= start)
        & (dates <= end)
        & (df_mov["Dominio"] == "PERSONAL")
        & (df_mov["EsEgresoEconomico"] == 1)
        & (df_mov["EsPresupuestable"] == 1)
    ]
    values = df.groupby("IdCategoria")["MontoUSD"].sum()
    return values.reindex(id_categories, fill_value=0.0).astype(float)


def _category_flags(df_mov: pd.DataFrame) -> pd.DataFrame:
    flag_cols = ["EsDeuda", "NaturalezaFinanciera"]
    available = [c for c in flag_cols if c in df_mov.columns]
    if not available:
        return pd.DataFrame(columns=["IdCategoria", "HasDebt", "Nature"])
    rows = []
    for idcat, grp in df_mov.groupby("IdCategoria"):
        rows.append(
            {
                "IdCategoria": idcat,
                "HasDebt": int(grp.get("EsDeuda", pd.Series([0])).fillna(0).astype(int).max() == 1),
                "Nature": str(grp.get("NaturalezaFinanciera", pd.Series([""])).mode().iloc[0]),
            }
        )
    return pd.DataFrame(rows)


def _classify_type(row: pd.Series) -> str:
    cat = str(row["Categoria"]).lower()
    sub = str(row["Subcategoria"]).lower()
    active_months = int(row["ActiveMonths"])
    hist_months = int(row["HistoryMonths"])
    freq = _safe_div(active_months, hist_months)
    cv = float(row["HistCV"])

    if bool(row.get("HasDebt", 0)) or "deuda" in cat or "cashea" in cat:
        return "DEBT"
    if any(token in cat for token in ["telecomunicaciones", "suscripciones"]):
        return "FIXED"
    if cat == "salud":
        return "SPARSE" if active_months <= 2 or freq < 0.75 else "VARIABLE"
    if cat == "alimentación":
        return "VARIABLE"
    if cat == "movilidad":
        return "VARIABLE"
    if freq >= 0.75 and cv <= 0.35 and float(row["MedianaHistorica"]) > 0:
        return "FIXED"
    if hist_months > 0 and (freq <= 0.35 or (active_months <= 1 and "mercado" not in sub)):
        return "SPARSE"
    if any(token in cat for token in ["tecnología", "vestimenta", "moto"]):
        return "SPARSE"
    return "VARIABLE"


def _confidence_details(row: pd.Series, ctx: ForecastContext) -> Tuple[int, str, str]:
    hist_months = int(row["HistoryMonths"])
    active_months = int(row["ActiveMonths"])
    cv = float(row["HistCV"])
    has_comparison = float(row["GastoAnteriorMismoPeriodo"]) > 0
    elapsed_ratio = ctx.elapsed_days / ctx.days_in_month

    score = 0
    reasons = []
    if hist_months >= 3:
        score += 2
        reasons.append(f"{hist_months} meses historicos")
    elif hist_months >= 2:
        score += 1
        reasons.append(f"{hist_months} meses historicos")
    else:
        reasons.append("historico menor a 2 meses")
    if active_months >= 2:
        score += 1
        reasons.append(f"{active_months} meses activos")
    else:
        reasons.append(f"{active_months} mes(es) activo(s)")
    if cv <= 0.45:
        score += 1
        reasons.append("baja dispersion")
    else:
        reasons.append("alta dispersion")
    if elapsed_ratio >= 0.45:
        score += 1
        reasons.append("avance de mes suficiente")
    if has_comparison:
        score += 1
        reasons.append("comparable MTD previo")
    else:
        reasons.append("sin comparable MTD previo")

    if score >= 5:
        confidence = "HIGH"
    elif score >= 3:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    return score, confidence, f"{confidence}: " + ", ".join(reasons)


def _confidence(row: pd.Series, ctx: ForecastContext) -> str:
    return _confidence_details(row, ctx)[1]


def _apply_type_overrides(evidence: pd.DataFrame, forecast_rules: pd.DataFrame) -> pd.DataFrame:
    if forecast_rules.empty:
        evidence["TipoForecastAntes"] = evidence["TipoForecast"]
        return evidence

    out = evidence.copy()
    out["TipoForecastAntes"] = out["TipoForecast"]
    overrides = forecast_rules.set_index("IdCategoria")["TipoForecastOverride"]
    override_values = overrides.reindex(out.index).fillna("")
    valid = override_values.isin(["FIXED", "VARIABLE", "DEBT", "SPARSE"])
    out.loc[valid, "TipoForecast"] = override_values[valid]
    return out


def _default_rule_values(row: pd.Series) -> pd.Series:
    forecast_type = str(row["TipoForecast"]).upper()
    cat = str(row["Categoria"]).lower()
    sub = str(row["Subcategoria"]).lower()

    if forecast_type in ["DEBT", "FIXED"]:
        flex = "NONE"
        essential = 1
    elif forecast_type == "SPARSE":
        flex = "HIGH"
        essential = 0
    else:
        flex = "MEDIUM"
        essential = 0

    if cat in ["alimentación", "movilidad"]:
        flex = "MEDIUM"
        essential = 1 if sub in ["mercado / hogar", "transporte público", "traslado personal"] else 0
    if cat in ["ocio", "vestimenta", "tecnología", "moto"]:
        flex = "HIGH"
        essential = 0
    if cat == "salud":
        flex = "MEDIUM" if sub == "medicinas" else "HIGH"
        essential = 1 if sub == "medicinas" else 0

    factor_realistic, factor_aggressive = FLEXIBILITY_FACTORS[flex]
    if forecast_type in ["DEBT", "FIXED"] and essential:
        factor_realistic, factor_aggressive = 1.0, 1.0

    return pd.Series(
        {
            "Flexibilidad": flex,
            "EsEsencial": essential,
            "FactorRealistic": factor_realistic,
            "FactorAggressive": factor_aggressive,
            "FloorUSD": 0.0,
            "CapUSD": np.nan,
        }
    )


def _attach_forecast_rules(evidence: pd.DataFrame, forecast_rules: pd.DataFrame) -> pd.DataFrame:
    out = evidence.copy()
    defaults = out.apply(_default_rule_values, axis=1)
    for col in defaults.columns:
        out[col] = defaults[col]

    if forecast_rules.empty:
        return out

    rules = forecast_rules.set_index("IdCategoria")
    for col in ["Flexibilidad", "EsEsencial", "FactorRealistic", "FactorAggressive", "FloorUSD", "CapUSD"]:
        override = rules[col].reindex(out.index)
        if col in ["Flexibilidad"]:
            out[col] = override.fillna(out[col]).replace("", np.nan).fillna(out[col])
        elif col == "CapUSD":
            out[col] = override.combine_first(out[col])
        else:
            out[col] = override.combine_first(out[col])

    out["Flexibilidad"] = out["Flexibilidad"].astype(str).str.upper()
    out.loc[~out["Flexibilidad"].isin(FLEXIBILITY_FACTORS), "Flexibilidad"] = "MEDIUM"
    out["EsEsencial"] = pd.to_numeric(out["EsEsencial"], errors="coerce").fillna(0).astype(int)
    for col in ["FactorRealistic", "FactorAggressive", "FloorUSD", "CapUSD"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["FloorUSD"] = out["FloorUSD"].fillna(0.0)
    return out


def _clamp_budget(value: float, floor: float, cap: float, upper: float | None = None) -> float:
    result = max(_round_money(value), _round_money(floor))
    if pd.notna(cap) and cap >= 0:
        result = min(result, float(cap))
    if upper is not None:
        result = min(result, float(upper))
        result = max(result, _round_money(floor))
    return _round_money(result)


def _scenario_budgets(row: pd.Series) -> Tuple[float, float, float]:
    forecast = float(row["ForecastProximoMes"])
    floor = float(row["FloorUSD"])
    cap = row["CapUSD"]
    current = _clamp_budget(forecast, floor, cap)
    realistic = _clamp_budget(current * float(row["FactorRealistic"]), floor, cap, upper=current)
    aggressive = _clamp_budget(realistic * float(row["FactorAggressive"]), floor, cap, upper=realistic)
    return current, realistic, aggressive


def _base_forecast(row: pd.Series, ctx: ForecastContext) -> Tuple[float, float, str]:
    elapsed_ratio = ctx.elapsed_days / ctx.days_in_month
    current_mtd = float(row["GastoActualMTD"])
    prev_same = float(row["GastoAnteriorMismoPeriodo"])
    prev_full = float(row["GastoMesAnteriorCompleto"])
    hist_mean = float(row["PromedioHistorico"])
    hist_median = float(row["MedianaHistorica"])
    current_budget = float(row["MontoPresupuestadoUSD"])
    baseline = float(row["BaselineHistorico"])
    forecast_type = row["TipoForecast"]

    run_rate = _safe_div(current_mtd, elapsed_ratio, current_mtd)
    trend_ratio = np.clip(_safe_div(current_mtd, prev_same, 1.0), 0.35, 2.2)
    pattern_projection = prev_full * trend_ratio if prev_full > 0 and prev_same > 0 else run_rate
    blended_projection = (0.50 * run_rate) + (0.50 * pattern_projection)
    weight_current = ctx.elapsed_days / (ctx.elapsed_days + SHRINKAGE_K_DAYS)

    if forecast_type == "FIXED":
        fixed_base = max(hist_median, prev_full, current_budget)
        close = max(current_mtd, fixed_base)
        next_month = max(hist_median, prev_full, current_budget, close * 0.85)
        method = "FIXED_LAST_MEDIAN_BUDGET"
    elif forecast_type == "DEBT":
        debt_base = max(prev_full, hist_median, current_budget)
        close = max(current_mtd, debt_base)
        next_month = max(current_budget, debt_base, current_mtd)
        method = "DEBT_OBLIGATION_BUDGET_HISTORY"
    elif forecast_type == "SPARSE":
        active_median = float(row["MedianaMesesConActividad"])
        frequency = float(row["ActivityFrequency"])
        sparse_base = active_median * min(max(frequency, 0.15), 0.75)
        close = max(current_mtd, min(blended_projection, max(active_median, current_mtd)))
        next_month = max(sparse_base, current_budget * 0.35 if current_budget > 0 else 0.0)
        method = "SPARSE_FREQUENCY_ACTIVE_MEDIAN"
    else:
        close = (weight_current * blended_projection) + ((1 - weight_current) * baseline)
        next_month = (0.55 * baseline) + (0.35 * close) + (0.10 * prev_full)
        method = f"VARIABLE_SHRINKAGE_K{SHRINKAGE_K_DAYS}"

    return _round_money(close), _round_money(next_month), method


def _default_scenario_factor(scenario: str, forecast_type: str, categoria: str) -> float:
    if scenario == "CURRENT":
        return 1.0
    if forecast_type in ["FIXED", "DEBT"]:
        return 1.0
    cat = categoria.lower()
    if scenario == "REALISTIC":
        if forecast_type == "SPARSE":
            return 0.70
        if any(token in cat for token in ["alimentación", "movilidad"]):
            return 0.94
        return 0.90
    if scenario == "AGGRESSIVE":
        if forecast_type == "SPARSE":
            return 0.45
        if any(token in cat for token in ["alimentación", "movilidad"]):
            return 0.82
        return 0.75
    return 1.0


def _apply_budget_rules_to_suggested(df: pd.DataFrame, rules_df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if rules_df.empty:
        return out

    for scenario in ["REALISTIC", "AGGRESSIVE"]:
        sc_rules = rules_df[rules_df["Scenario"] == scenario]
        if sc_rules.empty:
            continue

        for _, rule in sc_rules.iterrows():
            cat = str(rule["Categoria"]).strip()
            sub = str(rule["Subcategoria"]).strip()
            rtype = str(rule["RuleType"]).strip()
            value = float(rule["Value"])
            mask_cat = (out["Escenario"] == scenario) & (out["Categoria"] == cat)

            if rtype == "KEEP_CURRENT":
                continue
            if rtype == "USER_REQUIRED":
                out.loc[mask_cat, "PresupuestoSugeridoUSD"] = value
                continue
            if rtype == "FIXED":
                if sub == "*":
                    rows = out[mask_cat]
                    total = rows["ForecastProximoMes"].sum()
                    if total > 0 and len(rows) > 0:
                        out.loc[rows.index, "PresupuestoSugeridoUSD"] = rows["ForecastProximoMes"] / total * value
                    elif len(rows) > 0:
                        out.loc[rows.index, "PresupuestoSugeridoUSD"] = value / len(rows)
                else:
                    out.loc[mask_cat & (out["Subcategoria"] == sub), "PresupuestoSugeridoUSD"] = value
            if rtype == "DISTRIBUTE_GROUP":
                if sub == "DISTRIBUTE_NON_MERCADO":
                    rows = out[mask_cat & (out["Subcategoria"] != "Mercado / Hogar")]
                else:
                    rows = out[mask_cat]
                total = rows["ForecastProximoMes"].sum()
                if total > 0 and len(rows) > 0:
                    out.loc[rows.index, "PresupuestoSugeridoUSD"] = rows["ForecastProximoMes"] / total * value

    out["PresupuestoSugeridoUSD"] = out["PresupuestoSugeridoUSD"].apply(_round_money)
    out["FactorEscenario"] = out.apply(
        lambda r: round(_safe_div(r["PresupuestoSugeridoUSD"], r["ForecastProximoMes"], 1.0), 4)
        if float(r["ForecastProximoMes"]) > 0
        else (0.0 if float(r["PresupuestoSugeridoUSD"]) == 0 else 1.0),
        axis=1,
    )
    return out


def extend_presupuesto_with_forecast(
    df_presupuesto: pd.DataFrame,
    df_movimientos: pd.DataFrame,
    config_dir: str,
    output_dir: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    ctx = _planning_context(df_movimientos)
    df = df_presupuesto[df_presupuesto["Escenario"].isin(SCENARIOS)].copy()
    id_categories = pd.Index(df["IdCategoria"].drop_duplicates())
    forecast_rules = _load_forecast_rules(config_dir)

    prev_month = ctx.current_month - pd.DateOffset(months=1)
    prev_month_end = prev_month + pd.offsets.MonthEnd(0)
    prev_equiv_day = min(ctx.cut_date.day, calendar.monthrange(prev_month.year, prev_month.month)[1])
    prev_equiv_end = pd.Timestamp(prev_month.year, prev_month.month, prev_equiv_day)

    current_mtd = _sum_between(df_movimientos, ctx.current_month, ctx.cut_date, id_categories)
    prev_same = _sum_between(df_movimientos, prev_month, prev_equiv_end, id_categories)
    prev_full = _sum_between(df_movimientos, prev_month, prev_month_end, id_categories)
    hist_matrix = _monthly_matrix(df_movimientos, id_categories, ctx)

    evidence = df.drop_duplicates("IdCategoria")[
        ["IdCategoria", "Dominio", "Categoria", "Subcategoria", "TitularGasto"]
    ].set_index("IdCategoria")
    evidence["GastoActualMTD"] = current_mtd
    evidence["GastoAnteriorMismoPeriodo"] = prev_same
    evidence["GastoMesAnteriorCompleto"] = prev_full

    if hist_matrix.empty:
        evidence["PromedioHistorico"] = 0.0
        evidence["MedianaHistorica"] = 0.0
        evidence["MedianaMesesConActividad"] = 0.0
        evidence["HistoryMonths"] = 0
        evidence["ActiveMonths"] = 0
        evidence["ActivityFrequency"] = 0.0
        evidence["HistCV"] = 9.99
    else:
        evidence["PromedioHistorico"] = hist_matrix.mean(axis=1)
        evidence["MedianaHistorica"] = hist_matrix.median(axis=1)
        active = hist_matrix.where(hist_matrix > 0)
        evidence["MedianaMesesConActividad"] = active.median(axis=1).fillna(0.0)
        evidence["HistoryMonths"] = hist_matrix.shape[1]
        evidence["ActiveMonths"] = (hist_matrix > 0).sum(axis=1)
        evidence["ActivityFrequency"] = evidence["ActiveMonths"] / max(hist_matrix.shape[1], 1)
        mean = hist_matrix.mean(axis=1)
        evidence["HistCV"] = (hist_matrix.std(axis=1) / mean.replace(0, np.nan)).fillna(9.99)

    flags = _category_flags(df_movimientos).set_index("IdCategoria")
    evidence = evidence.join(flags[["HasDebt"]], how="left")
    evidence["HasDebt"] = evidence["HasDebt"].fillna(0).astype(int)
    evidence["VariacionMismoPeriodoPct"] = evidence.apply(
        lambda r: round((_safe_div(r["GastoActualMTD"] - r["GastoAnteriorMismoPeriodo"], r["GastoAnteriorMismoPeriodo"], 0.0)) * 100, 2)
        if float(r["GastoAnteriorMismoPeriodo"]) > 0
        else np.nan,
        axis=1,
    )

    budget_by_id = df[df["Escenario"] == "CURRENT"].set_index("IdCategoria")["MontoPresupuestadoUSD"]
    evidence["MontoPresupuestadoUSD"] = budget_by_id.reindex(evidence.index).fillna(0.0)
    evidence["BaselineHistorico"] = evidence[["MedianaHistorica", "PromedioHistorico", "GastoMesAnteriorCompleto", "MontoPresupuestadoUSD"]].max(axis=1)
    evidence["TipoForecast"] = evidence.apply(_classify_type, axis=1)
    evidence = _apply_type_overrides(evidence, forecast_rules)

    projections = evidence.apply(lambda row: _base_forecast(row, ctx), axis=1)
    evidence["ProyeccionCierreMesActual"] = projections.apply(lambda x: x[0])
    evidence["ForecastProximoMes"] = projections.apply(lambda x: x[1])
    evidence["MetodoPrediccion"] = projections.apply(lambda x: x[2])
    confidence = evidence.apply(lambda row: _confidence_details(row, ctx), axis=1)
    evidence["ConfidenceScore"] = confidence.apply(lambda x: x[0])
    evidence["ConfianzaPrediccion"] = confidence.apply(lambda x: x[1])
    evidence["ConfidenceReason"] = confidence.apply(lambda x: x[2])
    evidence = _attach_forecast_rules(evidence, forecast_rules)
    scenario_values = evidence.apply(lambda row: _scenario_budgets(row), axis=1)
    evidence["Budget_CURRENT"] = scenario_values.apply(lambda x: x[0])
    evidence["Budget_REALISTIC"] = scenario_values.apply(lambda x: x[1])
    evidence["Budget_AGGRESSIVE"] = scenario_values.apply(lambda x: x[2])
    evidence["PresupuestoBaseForecastUSD"] = evidence["Budget_CURRENT"]

    df = df.merge(
        evidence[
            [
                "GastoActualMTD",
                "GastoAnteriorMismoPeriodo",
                "GastoMesAnteriorCompleto",
                "PromedioHistorico",
                "MedianaHistorica",
                "BaselineHistorico",
                "VariacionMismoPeriodoPct",
                "ProyeccionCierreMesActual",
                "ForecastProximoMes",
                "MetodoPrediccion",
                "ConfianzaPrediccion",
                "ConfidenceScore",
                "ConfidenceReason",
                "TipoForecastAntes",
                "TipoForecast",
                "Flexibilidad",
                "EsEsencial",
                "FactorRealistic",
                "FactorAggressive",
                "FloorUSD",
                "CapUSD",
                "PresupuestoBaseForecastUSD",
                "Budget_CURRENT",
                "Budget_REALISTIC",
                "Budget_AGGRESSIVE",
            ]
        ],
        left_on="IdCategoria",
        right_index=True,
        how="left",
    )

    df["MesActual"] = ctx.current_month.date()
    df["MesPlan"] = ctx.plan_month.date()
    df["FechaCorte"] = ctx.cut_date.date()
    df["EstadoPlan"] = PLAN_STATUS
    df["PresupuestoSugeridoUSD"] = df.apply(
        lambda r: _round_money(r[f"Budget_{r['Escenario']}"]),
        axis=1,
    )
    df["FactorEscenario"] = df.apply(
        lambda r: round(_safe_div(r["PresupuestoSugeridoUSD"], r["PresupuestoBaseForecastUSD"], 1.0), 4)
        if float(r["PresupuestoBaseForecastUSD"]) > 0
        else (0.0 if float(r["PresupuestoSugeridoUSD"]) == 0 else 1.0),
        axis=1,
    )
    df["AjusteEscenarioUSD"] = df["PresupuestoSugeridoUSD"] - df["PresupuestoBaseForecastUSD"]

    overrides_path = _ensure_override_file(config_dir)
    overrides = pd.read_csv(overrides_path)
    if overrides.empty:
        df["PresupuestoManualUSD"] = np.nan
    else:
        overrides["MesPlan"] = pd.to_datetime(overrides["MesPlan"], errors="coerce").dt.date
        overrides["PresupuestoManualUSD"] = pd.to_numeric(overrides["PresupuestoManualUSD"], errors="coerce")
        valid_overrides = overrides[
            (overrides["MesPlan"] == ctx.plan_month.date())
            & (overrides["Escenario"].isin(SCENARIOS))
            & (overrides["PresupuestoManualUSD"].notna())
            & (overrides["PresupuestoManualUSD"] >= 0)
        ][["MesPlan", "Escenario", "IdCategoria", "PresupuestoManualUSD"]]
        df = df.merge(valid_overrides, on=["MesPlan", "Escenario", "IdCategoria"], how="left")

    df["PresupuestoFinalUSD"] = df["PresupuestoManualUSD"].where(
        df["PresupuestoManualUSD"].notna(), df["PresupuestoSugeridoUSD"]
    )
    money_cols = [
        "GastoActualMTD",
        "GastoAnteriorMismoPeriodo",
        "GastoMesAnteriorCompleto",
        "PromedioHistorico",
        "MedianaHistorica",
        "BaselineHistorico",
        "ProyeccionCierreMesActual",
        "ForecastProximoMes",
        "PresupuestoBaseForecastUSD",
        "PresupuestoSugeridoUSD",
        "PresupuestoManualUSD",
        "PresupuestoFinalUSD",
        "AjusteEscenarioUSD",
        "FloorUSD",
        "CapUSD",
    ]
    for col in money_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    audit_cols = [
        "MesActual",
        "MesPlan",
        "FechaCorte",
        "IdCategoria",
        "Categoria",
        "Subcategoria",
        "Escenario",
        "TipoForecast",
        "TipoForecastAntes",
        "Flexibilidad",
        "EsEsencial",
        "GastoActualMTD",
        "GastoAnteriorMismoPeriodo",
        "GastoMesAnteriorCompleto",
        "PromedioHistorico",
        "MedianaHistorica",
        "BaselineHistorico",
        "VariacionMismoPeriodoPct",
        "ProyeccionCierreMesActual",
        "ForecastProximoMes",
        "PresupuestoBaseForecastUSD",
        "FactorEscenario",
        "FactorRealistic",
        "FactorAggressive",
        "FloorUSD",
        "CapUSD",
        "PresupuestoSugeridoUSD",
        "PresupuestoManualUSD",
        "PresupuestoFinalUSD",
        "AjusteEscenarioUSD",
        "MetodoPrediccion",
        "ConfianzaPrediccion",
        "ConfidenceScore",
        "ConfidenceReason",
    ]
    audit_df = df[audit_cols].copy()
    audit_df.to_csv(os.path.join(output_dir, "plan_presupuesto_audit.csv"), index=False, encoding="utf-8-sig")

    summary = {
        "planning_enabled": ctx.planning_enabled,
        "current_month": str(ctx.current_month.date()),
        "plan_month": str(ctx.plan_month.date()),
        "cut_date": str(ctx.cut_date.date()),
        "overrides_applied": int(df["PresupuestoManualUSD"].notna().sum()),
        "new_columns": NEW_FACT_COLUMNS,
    }
    df = df.drop(columns=["Budget_CURRENT", "Budget_REALISTIC", "Budget_AGGRESSIVE"])
    return df, audit_df, summary
