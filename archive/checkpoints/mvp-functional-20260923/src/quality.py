import os
import json
import pandas as pd
from typing import Dict, Any, Tuple, List


def run_quality_checks(
    df_classified: pd.DataFrame,
    df_categorias: pd.DataFrame,
    df_dim_fecha: pd.DataFrame,
    df_presupuesto: pd.DataFrame,
    control_totals: Dict[str, Any],
    excluded_rows: List[Dict[str, Any]],
    output_dir: str
) -> Tuple[bool, Dict[str, Any], pd.DataFrame]:
    
    total_tx = len(df_classified)
    if total_tx == 0:
        raise ValueError("Structural failure: No transactions parsed from CSV.")

    required_cols = [
        "MovimientoId", "FechaKey", "Fecha", "TipoRial", "MontoOriginal", "MontoUSD",
        "IdCategoria", "Dominio", "Categoria", "Subcategoria", "TitularGasto",
        "ConfianzaClasificacion", "PendienteRevision"
    ]
    missing_cols = [col for col in required_cols if col not in df_classified.columns]
    if missing_cols:
        raise ValueError(f"Structural failure: Missing required columns {missing_cols}")

    # Star Schema Model Validations
    dim_cat_count = len(df_categorias)
    distinct_idcat_dim = df_categorias["IdCategoria"].nunique()

    movements_null_idcat = int(df_classified["IdCategoria"].isna().sum()) + int((df_classified["IdCategoria"] == "").sum())
    valid_dim_ids = set(df_categorias["IdCategoria"])
    movements_orphans = int((~df_classified["IdCategoria"].isin(valid_dim_ids)).sum())

    budget_rows = len(df_presupuesto)
    budget_null_idcat = int(df_presupuesto["IdCategoria"].isna().sum()) + int((df_presupuesto["IdCategoria"] == "").sum())
    budget_orphans = int((~df_presupuesto["IdCategoria"].isin(valid_dim_ids)).sum())

    # Date Dimension Validations
    fechakey_null = int(df_classified["FechaKey"].isna().sum())
    valid_date_keys = set(df_dim_fecha["FechaKey"])
    fechakey_orphans = int((~df_classified["FechaKey"].isin(valid_date_keys)).sum())
    dim_fecha_rows = len(df_dim_fecha)
    dim_fecha_unique = bool(dim_fecha_rows == df_dim_fecha["FechaKey"].nunique())

    date_min = str(df_classified["Fecha"].min())
    date_max = str(df_classified["Fecha"].max())

    high_cnt = int((df_classified["ConfianzaClasificacion"] == "HIGH").sum())
    med_cnt = int((df_classified["ConfianzaClasificacion"] == "MEDIUM").sum())
    manual_cnt = int((df_classified["ConfianzaClasificacion"] == "MANUAL_OVERRIDE").sum())
    unclassified_df = df_classified[df_classified["PendienteRevision"] == 1]
    unclassified_cnt = len(unclassified_df)

    classification_rate = round(((total_tx - unclassified_cnt) / total_tx) * 100, 2)

    exact_dup_cnt = int((df_classified["DuplicateType"] == "EXACT_DUPLICATE").sum())
    possible_dup_cnt = int((df_classified["DuplicateType"] == "POSSIBLE_DUPLICATE").sum())

    missing_fx_cnt = int((df_classified["MissingFxRate"] == 1).sum())
    imputed_fx_cnt = control_totals.get("imputed_fx_values", 0)

    # Export duplicados_revision.csv
    dup_df = df_classified[df_classified["DuplicateType"] != "NONE"].copy()
    if not dup_df.empty:
        dup_df["DuplicateGroup"] = dup_df.groupby(["Fecha", "TipoRial", "MontoOriginal", "MonedaOriginal"]).ngroup() + 1
        dup_cols = [
            "MovimientoId", "Fecha", "DescripcionOriginal", "TipoRial", "Cuenta",
            "MontoOriginal", "MonedaOriginal", "MontoUSD", "CategoriaRial",
            "DuplicateType", "DuplicateGroup"
        ]
        dup_df[dup_cols].to_csv(os.path.join(output_dir, "duplicados_revision.csv"), index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(columns=[
            "MovimientoId", "Fecha", "DescripcionOriginal", "TipoRial", "Cuenta",
            "MontoOriginal", "MonedaOriginal", "MontoUSD", "CategoriaRial",
            "DuplicateType", "DuplicateGroup"
        ]).to_csv(os.path.join(output_dir, "duplicados_revision.csv"), index=False, encoding="utf-8-sig")

    # Export clasificacion_medium_revision.csv
    medium_df = df_classified[df_classified["ConfianzaClasificacion"] == "MEDIUM"].copy()
    if not medium_df.empty:
        medium_audit = medium_df.groupby(["ReglaClasificacion", "CategoriaRial", "Categoria", "Subcategoria"]).agg(
            COUNT=("MovimientoId", "count"),
            SUM_MontoUSD=("MontoUSD", "sum")
        ).reset_index()
        medium_audit["SUM_MontoUSD"] = medium_audit["SUM_MontoUSD"].round(2)
        medium_audit.to_csv(os.path.join(output_dir, "clasificacion_medium_revision.csv"), index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(columns=["ReglaClasificacion", "CategoriaRial", "Categoria", "Subcategoria", "COUNT", "SUM_MontoUSD"]).to_csv(
            os.path.join(output_dir, "clasificacion_medium_revision.csv"), index=False, encoding="utf-8-sig"
        )

    # 5. SEMANTIC VALIDATION CHECKS (7 assertions)
    semantic_results = []
    
    tx_transfers = df_classified[df_classified["Categoria"] == "Transferencias"]
    c1 = (tx_transfers["EsIngresoEconomico"] == 0).all() and (tx_transfers["EsEgresoEconomico"] == 0).all() and (tx_transfers["EsConsumoPersonal"] == 0).all()
    semantic_results.append(("Transferencias_Internas", c1))

    tx_prestamo_ot = df_classified[df_classified["Subcategoria"] == "Préstamo otorgado"]
    c2 = (tx_prestamo_ot["EsConsumoPersonal"] == 0).all()
    semantic_results.append(("Prestamos_Otorgados_No_Consumo", c2))

    tx_prestamo_rec = df_classified[df_classified["Subcategoria"] == "Préstamo recibido"]
    c3 = (tx_prestamo_rec["EsIngresoEconomico"] == 0).all()
    semantic_results.append(("Prestamos_Recibidos_No_Ingreso", c3))

    tx_ahorro = df_classified[df_classified["Subcategoria"] == "Saldo inicial / ahorro previo"]
    c4 = (tx_ahorro["EsIngresoEconomico"] == 0).all()
    semantic_results.append(("Saldo_Inicial_No_Ingreso", c4))

    tx_negocio = df_classified[df_classified["Dominio"] == "NEGOCIO"]
    c5 = (tx_negocio["EsConsumoPersonal"] == 0).all()
    semantic_results.append(("PremiadosVE_No_Consumo_Personal", c5))

    tx_cashea_cuota = df_classified[df_classified["Subcategoria"] == "Cuota existente"]
    c6 = (tx_cashea_cuota["NaturalezaFinanciera"] == "PAGO_DEUDA").all() and (tx_cashea_cuota["EsConsumoPersonal"] == 0).all()
    semantic_results.append(("CASHEA_Cuota_Naturaleza_Deuda", c6))

    tx_cashea_inicial = df_classified[df_classified["Subcategoria"] == "Nueva compra / Inicial"]
    c7 = (tx_cashea_inicial["NaturalezaFinanciera"] == "EGRESO_CONSUMO").all() and (tx_cashea_inicial["EsConsumoPersonal"] == 1).all()
    semantic_results.append(("CASHEA_Inicial_Naturaleza_Consumo", c7))

    passed_semantic = sum(1 for name, ok in semantic_results if ok)
    total_semantic = len(semantic_results)

    personal_usd = float(df_classified[(df_classified["Dominio"] == "PERSONAL") & (df_classified["EsEgresoEconomico"] == 1)]["MontoUSD"].sum())
    business_usd = float(df_classified[(df_classified["Dominio"] == "NEGOCIO") & (df_classified["EsEgresoEconomico"] == 1)]["MontoUSD"].sum())
    patrimonial_usd = float(df_classified[df_classified["Dominio"] == "PATRIMONIAL"]["MontoUSD"].sum())

    quality_summary = {
        "status": "PASS" if unclassified_cnt == 0 and missing_fx_cnt == 0 and passed_semantic == total_semantic else "WARNING",
        "raw_rows_total": control_totals["raw_rows_total"],
        "transactions_total": total_tx,
        "excluded_rows": excluded_rows,
        "exact_duplicates": exact_dup_cnt,
        "possible_duplicates": possible_dup_cnt,
        "classified_high": high_cnt,
        "classified_medium": med_cnt,
        "classified_manual_override": manual_cnt,
        "unclassified": unclassified_cnt,
        "classification_rate": classification_rate,
        "missing_fx": missing_fx_cnt,
        "imputed_fx_values": imputed_fx_cnt,
        "dim_categories_count": dim_cat_count,
        "distinct_idcategoria": distinct_idcat_dim,
        "movements_null_idcat": movements_null_idcat,
        "movements_orphans": movements_orphans,
        "budget_rows": budget_rows,
        "budget_null_idcat": budget_null_idcat,
        "budget_idcat_orphans": budget_orphans,
        "fechakey_null": fechakey_null,
        "fechakey_orphans": fechakey_orphans,
        "dim_fecha_rows": dim_fecha_rows,
        "dim_fecha_unique": dim_fecha_unique,
        "date_min": date_min,
        "date_max": date_max,
        "domain_totals_usd": {
            "personal": round(personal_usd, 2),
            "business": round(business_usd, 2),
            "patrimonial": round(patrimonial_usd, 2)
        },
        "semantic_checks_passed": f"{passed_semantic}/{total_semantic}"
    }

    json_path = os.path.join(output_dir, "calidad_datos.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(quality_summary, f, indent=2, ensure_ascii=False)

    pending_path = os.path.join(output_dir, "pendientes_clasificacion.csv")
    cols_to_export_pending = [
        "MovimientoId", "FechaKey", "Fecha", "Hora", "TipoRial", "CategoriaRial", "SubcategoriaRial",
        "DescripcionOriginal", "Cuenta", "MonedaOriginal", "MontoOriginal", "MontoUSD",
        "IdCategoria", "Dominio", "Categoria", "Subcategoria", "TitularGasto", "NaturalezaFinanciera"
    ]
    cols_present = [c for c in cols_to_export_pending if c in unclassified_df.columns]
    unclassified_df[cols_present].to_csv(pending_path, index=False, encoding="utf-8-sig")

    return True, quality_summary, unclassified_df
