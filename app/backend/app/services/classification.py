from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from app.core.config import CONFIG_DIR, OUTPUT_DIR, PROJECT_ROOT
from app.services.etl import run_existing_pipeline


class CreateRulePayload(BaseModel):
    pattern: str = Field(..., description="Expresión regular o patrón para coincidir con la descripción")
    dominio: str = Field(default="PERSONAL")
    categoria: str = Field(...)
    subcategoria: str = Field(default="")
    titular: str = Field(default="MARLON")
    naturaleza: str = Field(default="EGRESO_CONSUMO")
    tipo_rial: str = Field(default="")
    categoria_rial: str = Field(default="")
    subcategoria_rial: str = Field(default="")
    priority: int = Field(default=10)
    es_presupuestable: int = Field(default=1)
    es_consumo_personal: int = Field(default=1)
    es_ingreso_economico: int = Field(default=0)
    es_egreso_economico: int = Field(default=1)
    es_negocio: int = Field(default=0)
    es_ahorro: int = Field(default=0)
    es_prestamo: int = Field(default=0)
    es_deuda: int = Field(default=0)
    es_transferencia: int = Field(default=0)
    es_reembolso: int = Field(default=0)


def suggest_pattern(desc: str) -> str:
    """Generates an intelligent regex pattern suggestion from a transaction description."""
    if not desc or not desc.strip():
        return "(?i).*"
    cleaned = re.sub(r"[^\w\s]", " ", desc, flags=re.UNICODE)
    words = [w for w in cleaned.split() if len(w) >= 3 and not w.isdigit()]
    stop_words = {
        "para", "este", "esta", "estos", "estas", "como", "desde", "hasta",
        "pago", "compra", "transferencia", "deposito", "abono", "gasto"
    }
    filtered = [w.lower() for w in words if w.lower() not in stop_words]
    if filtered:
        # Use first 2-3 most distinctive words
        tokens = filtered[:3]
        return f"(?i){'|'.join(re.escape(t) for t in tokens)}"
    return f"(?i){re.escape(desc.strip())}"


def get_pending_classifications() -> dict[str, Any]:
    file_path = OUTPUT_DIR / "pendientes_clasificacion.csv"
    if not file_path.exists():
        return {"total": 0, "items": []}

    try:
        df = pd.read_csv(file_path, dtype=str).fillna("")
    except Exception:
        return {"total": 0, "items": []}

    # Filter out blank rows
    valid_rows = df[df["DescripcionOriginal"].str.strip() != ""] if "DescripcionOriginal" in df.columns else df
    items = []
    for idx, row in valid_rows.iterrows():
        desc = str(row.get("DescripcionOriginal", "")).strip()
        monto_usd = 0.0
        try:
            monto_usd = float(str(row.get("MontoUSD", 0)).replace(",", "."))
        except (ValueError, TypeError):
            monto_usd = 0.0

        items.append({
            "id": str(row.get("MovimientoId", f"row_{idx}")),
            "fecha": str(row.get("Fecha", "")),
            "tipo_rial": str(row.get("TipoRial", "")),
            "categoria_rial": str(row.get("CategoriaRial", "")),
            "subcategoria_rial": str(row.get("SubcategoriaRial", "")),
            "descripcion": desc,
            "cuenta": str(row.get("Cuenta", "")),
            "monto_usd": monto_usd,
            "monto_original": str(row.get("MontoOriginal", "")),
            "moneda": str(row.get("MonedaOriginal", "")),
            "suggested_pattern": suggest_pattern(desc),
        })

    return {
        "total": len(items),
        "items": items,
    }


def get_rules() -> dict[str, Any]:
    rules_path = CONFIG_DIR / "category_rules.csv"
    if not rules_path.exists():
        return {"total": 0, "rules": []}

    df = pd.read_csv(rules_path, dtype=str).fillna("")
    rules = []
    for _, row in df.iterrows():
        rules.append({
            "rule_id": str(row.get("RuleId", "")),
            "priority": int(pd.to_numeric(row.get("Priority", 10), errors="coerce") or 10),
            "tipo_rial": str(row.get("TipoRial", "")),
            "categoria_rial": str(row.get("CategoriaRial", "")),
            "subcategoria_rial": str(row.get("SubcategoriaRial", "")),
            "pattern": str(row.get("PatternDescripcion", "")),
            "match_mode": str(row.get("MatchMode", "regex")),
            "dominio": str(row.get("Dominio", "")),
            "categoria": str(row.get("Categoria", "")),
            "subcategoria": str(row.get("Subcategoria", "")),
            "titular": str(row.get("TitularGasto", "")),
            "naturaleza": str(row.get("NaturalezaFinanciera", "")),
            "flags": {
                "es_presupuestable": int(row.get("EsPresupuestable", 1) or 0),
                "es_consumo_personal": int(row.get("EsConsumoPersonal", 1) or 0),
                "es_ingreso_economico": int(row.get("EsIngresoEconomico", 0) or 0),
                "es_egreso_economico": int(row.get("EsEgresoEconomico", 1) or 0),
                "es_negocio": int(row.get("EsNegocio", 0) or 0),
                "es_ahorro": int(row.get("EsAhorro", 0) or 0),
                "es_prestamo": int(row.get("EsPrestamo", 0) or 0),
                "es_deuda": int(row.get("EsDeuda", 0) or 0),
                "es_transferencia": int(row.get("EsTransferencia", 0) or 0),
                "es_reembolso": int(row.get("EsReembolso", 0) or 0),
            },
        })

    return {
        "total": len(rules),
        "rules": rules,
    }


def get_classification_options() -> dict[str, Any]:
    rules_path = CONFIG_DIR / "category_rules.csv"
    categorias: set[str] = set()
    subcategorias_by_cat: dict[str, set[str]] = {}

    if rules_path.exists():
        df_rules = pd.read_csv(rules_path, dtype=str).fillna("")
        for _, r in df_rules.iterrows():
            c = str(r.get("Categoria", "")).strip()
            s = str(r.get("Subcategoria", "")).strip()
            if c:
                categorias.add(c)
                if c not in subcategorias_by_cat:
                    subcategorias_by_cat[c] = set()
                if s:
                    subcategorias_by_cat[c].add(s)

    # Also pull from parquet if available
    parquet_cats = OUTPUT_DIR / "categorias.parquet"
    if parquet_cats.exists():
        try:
            df_cat = pd.read_parquet(parquet_cats)
            for _, r in df_cat.iterrows():
                c = str(r.get("Categoria", "")).strip()
                s = str(r.get("Subcategoria", "")).strip()
                if c:
                    categorias.add(c)
                    if c not in subcategorias_by_cat:
                        subcategorias_by_cat[c] = set()
                    if s:
                        subcategorias_by_cat[c].add(s)
        except Exception:
            pass

    return {
        "dominios": ["PERSONAL", "NEGOCIO", "PATRIMONIAL", "CONTROL"],
        "categorias": sorted(list(categorias)),
        "subcategorias": {k: sorted(list(v)) for k, v in subcategorias_by_cat.items()},
        "titulares": ["MARLON", "ANILET", "PREMIADOSVE", "NO_APLICA"],
        "naturalezas": [
            "EGRESO_CONSUMO",
            "INGRESOS_OPERATIVOS",
            "EGRESO_OPERATIVO",
            "PAGO_DEUDA",
            "PRESTAMO",
            "AHORRO",
            "CUENTA_POR_COBRAR",
            "TRANSFERENCIA_INTERNA",
            "PUBLICIDAD",
            "INVERSION",
            "VENTAS",
            "REEMBOLSO",
            "COMISION",
        ],
        "tipos_rial": ["", "Egreso", "Ingreso", "Transferencia (salida)", "Transferencia (entrada)"],
    }


def create_rule(payload: CreateRulePayload) -> dict[str, Any]:
    # Validate regex
    try:
        re.compile(payload.pattern)
    except re.error as e:
        raise ValueError(f"Expresión regular inválida: {str(e)}")

    rules_path = CONFIG_DIR / "category_rules.csv"
    if not rules_path.exists():
        raise FileNotFoundError("Archivo de reglas no encontrado.")

    df = pd.read_csv(rules_path, dtype=str).fillna("")

    # Determine next RuleId
    max_id = 0
    for rid in df["RuleId"]:
        match = re.match(r"R(\d+)", str(rid).strip())
        if match:
            num = int(match.group(1))
            if num > max_id:
                max_id = num

    new_rule_id = f"R{max_id + 1:03d}"

    # Auto-adjust flags based on nature if user kept standard defaults
    nat = payload.naturaleza.upper()
    es_ingreso = 1 if nat in ("INGRESOS_OPERATIVOS", "VENTAS") else payload.es_ingreso_economico
    es_egreso = 1 if nat in ("EGRESO_CONSUMO", "EGRESO_OPERATIVO", "PUBLICIDAD", "PAGO_DEUDA") else payload.es_egreso_economico
    es_negocio = 1 if nat in ("EGRESO_OPERATIVO", "PUBLICIDAD", "VENTAS") or payload.dominio == "NEGOCIO" else payload.es_negocio
    es_consumo = 1 if nat == "EGRESO_CONSUMO" and payload.dominio == "PERSONAL" else payload.es_consumo_personal
    es_deuda = 1 if nat == "PAGO_DEUDA" else payload.es_deuda
    es_prestamo = 1 if nat == "PRESTAMO" else payload.es_prestamo
    es_ahorro = 1 if nat == "AHORRO" else payload.es_ahorro
    es_transf = 1 if nat == "TRANSFERENCIA_INTERNA" else payload.es_transferencia
    es_presup = 1 if nat in ("EGRESO_CONSUMO", "EGRESO_OPERATIVO", "PUBLICIDAD", "PAGO_DEUDA") else payload.es_presupuestable

    new_row = {
        "RuleId": new_rule_id,
        "Priority": str(payload.priority),
        "TipoRial": payload.tipo_rial,
        "CategoriaRial": payload.categoria_rial,
        "SubcategoriaRial": payload.subcategoria_rial,
        "PatternDescripcion": payload.pattern,
        "MatchMode": "regex",
        "Dominio": payload.dominio,
        "Categoria": payload.categoria,
        "Subcategoria": payload.subcategoria,
        "TitularGasto": payload.titular,
        "NaturalezaFinanciera": payload.naturaleza,
        "EsPresupuestable": str(es_presup),
        "EsConsumoPersonal": str(es_consumo),
        "EsIngresoEconomico": str(es_ingreso),
        "EsEgresoEconomico": str(es_egreso),
        "EsNegocio": str(es_negocio),
        "EsAhorro": str(es_ahorro),
        "EsPrestamo": str(es_prestamo),
        "EsDeuda": str(es_deuda),
        "EsTransferencia": str(es_transf),
        "EsReembolso": str(payload.es_reembolso),
    }

    # Append to category_rules.csv
    # Write cleanly preserving column order
    cols = list(df.columns)
    row_df = pd.DataFrame([new_row])[cols]
    updated_df = pd.concat([df, row_df], ignore_index=True)
    updated_df.to_csv(rules_path, index=False, encoding="utf-8")

    # Run ETL pipeline to apply newly created rule across dataset
    etl_result = run_existing_pipeline(PROJECT_ROOT)

    pending_after = get_pending_classifications()

    return {
        "status": "PASS" if etl_result.returncode == 0 else "FAIL",
        "rule_id": new_rule_id,
        "pending_count_after": pending_after["total"],
        "message": f"Regla {new_rule_id} creada y pipeline re-ejecutado exitosamente.",
        "etl_returncode": etl_result.returncode,
    }


def delete_rule(rule_id: str) -> dict[str, Any]:
    rules_path = CONFIG_DIR / "category_rules.csv"
    if not rules_path.exists():
        raise FileNotFoundError("Archivo de reglas no encontrado.")

    df = pd.read_csv(rules_path, dtype=str).fillna("")
    if rule_id not in df["RuleId"].values:
        raise KeyError(f"Regla {rule_id} no encontrada.")

    updated_df = df[df["RuleId"] != rule_id]
    updated_df.to_csv(rules_path, index=False, encoding="utf-8")

    # Re-run ETL pipeline
    etl_result = run_existing_pipeline(PROJECT_ROOT)
    pending_after = get_pending_classifications()

    return {
        "status": "PASS" if etl_result.returncode == 0 else "FAIL",
        "rule_id": rule_id,
        "pending_count_after": pending_after["total"],
        "message": f"Regla {rule_id} eliminada y pipeline re-ejecutado exitosamente.",
    }
