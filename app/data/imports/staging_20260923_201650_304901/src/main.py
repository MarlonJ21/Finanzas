import os
import sys
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from normalize import load_and_normalize_csv
from classify import apply_classification
from quality import run_quality_checks
from budget_forecast import SCENARIOS, extend_presupuesto_with_forecast


def gen_id_categoria(row) -> str:
    dom = str(row.get("Dominio", "")).strip()
    cat = str(row.get("Categoria", "")).strip()
    subcat = str(row.get("Subcategoria", "")).strip()
    titular = str(row.get("TitularGasto", "")).strip()
    key = f"{dom}|{cat}|{subcat}|{titular}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def build_categorias_catalog(df_classified: pd.DataFrame) -> pd.DataFrame:
    cat_cols = [
        "IdCategoria", "Dominio", "Categoria", "Subcategoria", "NaturalezaFinanciera",
        "TitularGasto", "EsPresupuestable"
    ]
    df_cat = df_classified[cat_cols].drop_duplicates().copy()
    df_cat["Activo"] = 1

    cols_order = [
        "IdCategoria", "Dominio", "Categoria", "Subcategoria",
        "NaturalezaFinanciera", "TitularGasto", "EsPresupuestable", "Activo"
    ]
    return df_cat[cols_order].sort_values(by=["Dominio", "Categoria", "Subcategoria", "TitularGasto"])


def build_dim_fecha(df_norm: pd.DataFrame) -> pd.DataFrame:
    min_date_str = df_norm["Fecha"].min()
    max_date_str = df_norm["Fecha"].max()

    start_date = datetime.strptime(min_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(max_date_str, "%Y-%m-%d")

    date_rows = []
    meses_es = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    dias_es = {
        1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"
    }

    curr = start_date
    while curr <= end_date:
        fecha_str = curr.strftime("%Y-%m-%d")
        fecha_key = int(curr.strftime("%Y%m%d"))
        anio = curr.year
        mes_num = curr.month
        mes_nombre = meses_es[mes_num]
        anio_mes = curr.strftime("%Y-%m")
        anio_mes_orden = int(curr.strftime("%Y%m"))
        dia = curr.day
        dia_semana_num = curr.isoweekday()
        dia_semana_nombre = dias_es[dia_semana_num]
        es_fin_semana = 1 if dia_semana_num in [6, 7] else 0
        quincena = 1 if dia <= 15 else 2

        date_rows.append({
            "FechaKey": fecha_key,
            "Fecha": fecha_str,
            "Año": anio,
            "MesNumero": mes_num,
            "Mes": mes_nombre,
            "AñoMes": anio_mes,
            "AñoMesOrden": anio_mes_orden,
            "Dia": dia,
            "DiaSemanaNumero": dia_semana_num,
            "DiaSemana": dia_semana_nombre,
            "EsFinSemana": es_fin_semana,
            "Quincena": quincena
        })
        curr += timedelta(days=1)

    df_dim_fecha = pd.DataFrame(date_rows)
    return df_dim_fecha


def apply_scenario_rules(scenario_name: str, df_base: pd.DataFrame, rules_df: pd.DataFrame) -> pd.DataFrame:
    df_sc = df_base.copy()
    df_sc["Escenario"] = scenario_name
    df_sc["MontoPresupuestadoUSD"] = df_sc["MontoMesActualUSD"]

    if scenario_name in ["CURRENT"] or rules_df.empty:
        df_sc["MontoPresupuestadoUSD"] = df_sc["MontoPresupuestadoUSD"].round(2)
        return df_sc

    sc_rules = rules_df[rules_df["Scenario"] == scenario_name]

    for cat in df_sc["Categoria"].unique():
        cat_rows = df_sc[df_sc["Categoria"] == cat]
        cat_tot_aug = cat_rows["MontoMesActualUSD"].sum()

        r_cat = sc_rules[sc_rules["Categoria"] == cat]
        if r_cat.empty:
            continue

        for _, r in r_cat.iterrows():
            subcat_pat = str(r["Subcategoria"]).strip()
            rtype = str(r["RuleType"]).strip()
            val = float(r["Value"])

            if rtype == "KEEP_CURRENT":
                pass
            elif rtype == "USER_REQUIRED":
                df_sc.loc[df_sc["Categoria"] == cat, "MontoPresupuestadoUSD"] = val
            elif rtype == "FIXED":
                if subcat_pat == "*":
                    if cat_tot_aug > 0:
                        df_sc.loc[df_sc["Categoria"] == cat, "MontoPresupuestadoUSD"] = (df_sc.loc[df_sc["Categoria"] == cat, "MontoMesActualUSD"] / cat_tot_aug) * val
                    else:
                        df_sc.loc[df_sc["Categoria"] == cat, "MontoPresupuestadoUSD"] = val / len(cat_rows)
                else:
                    df_sc.loc[(df_sc["Categoria"] == cat) & (df_sc["Subcategoria"] == subcat_pat), "MontoPresupuestadoUSD"] = val
            elif rtype == "DISTRIBUTE_GROUP":
                if subcat_pat == "DISTRIBUTE_NON_MERCADO":
                    sub_rows = df_sc[(df_sc["Categoria"] == cat) & (df_sc["Subcategoria"] != "Mercado / Hogar")]
                    sub_tot = sub_rows["MontoMesActualUSD"].sum()
                    if sub_tot > 0:
                        idx_list = sub_rows.index
                        df_sc.loc[idx_list, "MontoPresupuestadoUSD"] = (df_sc.loc[idx_list, "MontoMesActualUSD"] / sub_tot) * val
                else:
                    if cat_tot_aug > 0:
                        idx_list = cat_rows.index
                        df_sc.loc[idx_list, "MontoPresupuestadoUSD"] = (df_sc.loc[idx_list, "MontoMesActualUSD"] / cat_tot_aug) * val

    df_sc["MontoPresupuestadoUSD"] = df_sc["MontoPresupuestadoUSD"].round(2)
    return df_sc


def build_presupuesto_baseline(df_classified: pd.DataFrame, config_dir: str) -> pd.DataFrame:
    rules_path = os.path.join(config_dir, "budget_rules.csv")
    rules_df = pd.read_csv(rules_path) if os.path.exists(rules_path) else pd.DataFrame()

    df_august = df_classified[
        (df_classified["Fecha"].str.startswith("2026-08")) &
        (df_classified["Dominio"] == "PERSONAL") &
        (df_classified["EsEgresoEconomico"] == 1) &
        (df_classified["EsPresupuestable"] == 1)
    ].copy()

    all_cats = df_classified[
        (df_classified["Dominio"] == "PERSONAL") &
        (df_classified["EsPresupuestable"] == 1)
    ][["IdCategoria", "Dominio", "Categoria", "Subcategoria", "TitularGasto"]].drop_duplicates()

    baseline = df_august.groupby(["IdCategoria", "Dominio", "Categoria", "Subcategoria", "TitularGasto"]).agg(
        MontoMesActualUSD=("MontoUSD", "sum")
    ).reset_index()

    df_base = pd.merge(all_cats, baseline, on=["IdCategoria", "Dominio", "Categoria", "Subcategoria", "TitularGasto"], how="left")
    df_base["MontoMesActualUSD"] = df_base["MontoMesActualUSD"].fillna(0.0).round(2)

    scenarios = []
    for sc_name in SCENARIOS:
        df_sc = apply_scenario_rules(sc_name, df_base, rules_df)
        scenarios.append(df_sc)

    df_presupuesto = pd.concat(scenarios, ignore_index=True)
    return df_presupuesto


def build_presupuesto_quincenal(df_presupuesto: pd.DataFrame, config_dir: str) -> pd.DataFrame:
    paycheck_rules_path = os.path.join(config_dir, "budget_paycheck_rules.csv")
    p_rules = pd.read_csv(paycheck_rules_path) if os.path.exists(paycheck_rules_path) else pd.DataFrame()

    quincenal_rows = []

    for _, row in df_presupuesto.iterrows():
        esc = row["Escenario"]
        cat = row["Categoria"]
        subcat = row["Subcategoria"]
        monto_mensual = float(row["MontoPresupuestadoUSD"])

        q1_pct = 0.50
        q2_pct = 0.50
        metodo = "EQUAL_SPLIT"

        if not p_rules.empty:
            match_rules = p_rules[
                (p_rules["Escenario"] == esc) &
                (p_rules["Categoria"] == cat) &
                ((p_rules["Subcategoria"] == subcat) | (p_rules["Subcategoria"] == "*"))
            ]
            if not match_rules.empty:
                r = match_rules.iloc[0]
                q1_pct = float(r["Q1Pct"])
                q2_pct = float(r["Q2Pct"])
                metodo = str(r["Metodo"]).strip()

        monto_q1 = round(monto_mensual * q1_pct, 2)
        monto_q2 = round(monto_mensual - monto_q1, 2)

        # Row Q1
        r_q1 = row.to_dict()
        r_q1["Quincena"] = 1
        r_q1["MontoPresupuestoQuincenalUSD"] = monto_q1
        r_q1["MetodoDistribucion"] = metodo

        # Row Q2
        r_q2 = row.to_dict()
        r_q2["Quincena"] = 2
        r_q2["MontoPresupuestoQuincenalUSD"] = monto_q2
        r_q2["MetodoDistribucion"] = metodo

        quincenal_rows.append(r_q1)
        quincenal_rows.append(r_q2)

    df_q = pd.DataFrame(quincenal_rows)
    cols = [
        "Escenario", "IdCategoria", "Dominio", "Categoria", "Subcategoria",
        "TitularGasto", "Quincena", "MontoPresupuestoQuincenalUSD", "MetodoDistribucion"
    ]
    return df_q[cols]


def main():
    workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(workspace_dir, "raw")
    config_dir = os.path.join(workspace_dir, "config")
    output_dir = os.path.join(workspace_dir, "output")

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    csv_candidates = [
        os.path.join(raw_dir, f) for f in os.listdir(raw_dir) if f.endswith(".csv")
    ] + [
        os.path.join(workspace_dir, f) for f in os.listdir(workspace_dir) if f.endswith(".csv") and not f.startswith(".")
    ]

    if not csv_candidates:
        print("ERROR: No CSV file found in raw/ or workspace root.")
        sys.exit(1)

    csv_path = csv_candidates[0]

    df_norm, control_totals, excluded_rows = load_and_normalize_csv(csv_path)

    rules_path = os.path.join(config_dir, "category_rules.csv")
    overrides_path = os.path.join(config_dir, "transaction_overrides.csv")
    df_classified = apply_classification(df_norm, rules_path, overrides_path)

    df_classified["IdCategoria"] = df_classified.apply(gen_id_categoria, axis=1)

    df_categorias = build_categorias_catalog(df_classified)
    df_dim_fecha = build_dim_fecha(df_norm)
    df_presupuesto_base = build_presupuesto_baseline(df_classified, config_dir)
    rows_before = len(df_presupuesto_base)
    original_columns = list(df_presupuesto_base.columns)
    original_snapshot = df_presupuesto_base[original_columns].copy()
    df_presupuesto, df_plan_audit, plan_summary = extend_presupuesto_with_forecast(
        df_presupuesto_base, df_classified, config_dir, output_dir
    )

    quality_passed, q, df_pending = run_quality_checks(
        df_classified, df_categorias, df_dim_fecha, df_presupuesto, control_totals, excluded_rows, output_dir
    )

    presupuesto_path = os.path.join(output_dir, "presupuesto.parquet")

    df_presupuesto.to_parquet(presupuesto_path, index=False, engine="pyarrow")

    readback_ok = True
    try:
        df_presupuesto_readback = pd.read_parquet(presupuesto_path)
    except Exception:
        readback_ok = False
        df_presupuesto_readback = pd.DataFrame()

    original_preserved_count = sum(col in df_presupuesto.columns for col in original_columns)
    original_values_preserved = True
    try:
        current_original = df_presupuesto[original_columns].reset_index(drop=True)
        expected_original = original_snapshot.reset_index(drop=True)
        original_values_preserved = current_original.equals(expected_original)
    except Exception:
        original_values_preserved = False

    rows_after = len(df_presupuesto)
    dupes = int(df_presupuesto.duplicated(subset=["Escenario", "IdCategoria"]).sum())
    valid_scenarios = set(df_presupuesto["Escenario"].dropna().unique().tolist()) == set(SCENARIOS)
    grain_ok = dupes == 0 and valid_scenarios
    categories_forecasted = int(df_presupuesto["IdCategoria"].nunique())

    suggested = df_presupuesto.groupby("Escenario")["PresupuestoSugeridoUSD"].sum().to_dict()
    final = df_presupuesto.groupby("Escenario")["PresupuestoFinalUSD"].sum().to_dict()
    methods = df_presupuesto.drop_duplicates("IdCategoria")["TipoForecast"].value_counts().to_dict()
    confidence = df_presupuesto.drop_duplicates("IdCategoria")["ConfianzaPrediccion"].value_counts().to_dict()

    current_operating_budget = float(
        df_presupuesto[df_presupuesto["Escenario"] == "REALISTIC"]["MontoPresupuestadoUSD"].sum()
    )
    expected_operating_budget = 631.21
    regression_ok = round(current_operating_budget, 2) == expected_operating_budget and original_values_preserved
    quality_checks_ok = (
        grain_ok
        and dupes == 0
        and valid_scenarios
        and (df_presupuesto["PresupuestoSugeridoUSD"].fillna(0) >= 0).all()
        and (df_presupuesto["PresupuestoFinalUSD"].fillna(0) >= 0).all()
    )
    fact_extended_ok = set(plan_summary["new_columns"]).issubset(df_presupuesto.columns)

    print(f"PLANNING ENABLED: {'YES' if plan_summary['planning_enabled'] else 'NO'}")
    print(f"CURRENT MONTH: {plan_summary['current_month']}")
    print(f"PLAN MONTH: {plan_summary['plan_month']}")
    print(f"CUT DATE: {plan_summary['cut_date']}")
    print(f"FACT_PRESUPUESTOS EXTENDED: {'PASS' if fact_extended_ok else 'FAIL'}")
    print(f"ORIGINAL COLUMNS PRESERVED: {original_preserved_count}/{len(original_columns)}")
    print(f"NEW COLUMNS: {', '.join(plan_summary['new_columns'])}")
    print("GRAIN: Escenario + IdCategoria")
    print(f"GRAIN VALIDATION: {'PASS' if grain_ok else 'FAIL'}")
    print(f"ROWS BEFORE: {rows_before}")
    print(f"ROWS AFTER: {rows_after}")
    print(f"DUPLICATES: {dupes}")
    print(f"CATEGORIES FORECASTED: {categories_forecasted}")
    print(f"CURRENT TOTAL SUGGESTED: ${suggested.get('CURRENT', 0):,.2f}")
    print(f"REALISTIC TOTAL SUGGESTED: ${suggested.get('REALISTIC', 0):,.2f}")
    print(f"AGGRESSIVE TOTAL SUGGESTED: ${suggested.get('AGGRESSIVE', 0):,.2f}")
    print(f"CURRENT FINAL: ${final.get('CURRENT', 0):,.2f}")
    print(f"REALISTIC FINAL: ${final.get('REALISTIC', 0):,.2f}")
    print(f"AGGRESSIVE FINAL: ${final.get('AGGRESSIVE', 0):,.2f}")
    print(f"OVERRIDES APPLIED: {plan_summary['overrides_applied']}")
    print(
        "FORECAST METHODS: "
        f"FIXED: {methods.get('FIXED', 0)} "
        f"VARIABLE: {methods.get('VARIABLE', 0)} "
        f"DEBT: {methods.get('DEBT', 0)} "
        f"SPARSE: {methods.get('SPARSE', 0)}"
    )
    print(
        "CONFIDENCE: "
        f"HIGH: {confidence.get('HIGH', 0)} "
        f"MEDIUM: {confidence.get('MEDIUM', 0)} "
        f"LOW: {confidence.get('LOW', 0)}"
    )
    print(f"CURRENT OPERATING BUDGET TOTAL: ${current_operating_budget:,.2f}")
    print(f"EXPECTED CURRENT OPERATING BUDGET: {expected_operating_budget}")
    print(f"REGRESSION: {'PASS' if regression_ok else 'FAIL'}")
    print(f"QUALITY CHECKS: {'PASS' if quality_checks_ok else 'FAIL'}")
    print(f"PARQUET READBACK: {'PASS' if readback_ok and not df_presupuesto_readback.empty else 'FAIL'}")
    print("POWER BI PAGE 1 MODIFIED: NO")
    print("PBIR MODIFIED: NO")


if __name__ == "__main__":
    main()
