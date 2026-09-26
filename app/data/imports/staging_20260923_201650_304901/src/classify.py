import os
import re
import pandas as pd
from typing import Dict, Any, List


def load_overrides(overrides_path: str) -> pd.DataFrame:
    if os.path.exists(overrides_path):
        try:
            return pd.read_csv(overrides_path, dtype=str).fillna("")
        except Exception:
            pass
    return pd.DataFrame()


def load_rules(rules_path: str) -> pd.DataFrame:
    if os.path.exists(rules_path):
        df_rules = pd.read_csv(rules_path, dtype=str).fillna("")
        df_rules["Priority"] = pd.to_numeric(df_rules["Priority"], errors="coerce").fillna(99)
        return df_rules.sort_values(by="Priority")
    return pd.DataFrame()


def apply_classification(df_norm: pd.DataFrame, rules_path: str, overrides_path: str) -> pd.DataFrame:
    df_overrides = load_overrides(overrides_path)
    df_rules = load_rules(rules_path)

    override_by_id = {}
    override_by_desc = {}
    if not df_overrides.empty:
        for _, row in df_overrides.iterrows():
            m_id = str(row.get("MovimientoId", "")).strip()
            desc = str(row.get("DescripcionExacta", "")).strip()
            if m_id:
                override_by_id[m_id] = row
            if desc:
                override_by_desc[desc] = row

    classified_rows = []

    for idx, r in df_norm.iterrows():
        mov_id = r["MovimientoId"]
        desc = r["DescripcionOriginal"]
        tipo_rial = r["TipoRial"]
        cat_rial = r["CategoriaRial"]
        subcat_rial = r["SubcategoriaRial"]

        classified = None
        regla_id = ""
        is_manual_override = False

        # 1. Manual Override (Highest Precedence)
        if mov_id in override_by_id:
            ov = override_by_id[mov_id]
            regla_id = "MANUAL_OVERRIDE"
            is_manual_override = True
            classified = {
                "Dominio": ov.get("Dominio", ""),
                "Categoria": ov.get("Categoria", ""),
                "Subcategoria": ov.get("Subcategoria", ""),
                "TitularGasto": ov.get("TitularGasto", "MARLON"),
                "NaturalezaFinanciera": ov.get("NaturalezaFinanciera", "EGRESO_CONSUMO"),
                "ConfianzaClasificacion": "MANUAL_OVERRIDE",
                "PendienteRevision": 0,
                "EsPresupuestable": int(ov.get("EsPresupuestable", 1)),
                "EsConsumoPersonal": int(ov.get("EsConsumoPersonal", 1)),
                "EsIngresoEconomico": int(ov.get("EsIngresoEconomico", 0)),
                "EsEgresoEconomico": int(ov.get("EsEgresoEconomico", 1)),
                "EsNegocio": int(ov.get("EsNegocio", 0)),
                "EsAhorro": int(ov.get("EsAhorro", 0)),
                "EsPrestamo": int(ov.get("EsPrestamo", 0)),
                "EsDeuda": int(ov.get("EsDeuda", 0)),
                "EsTransferencia": int(ov.get("EsTransferencia", 0)),
                "EsReembolso": int(ov.get("EsReembolso", 0)),
            }
        elif desc in override_by_desc:
            ov = override_by_desc[desc]
            regla_id = "MANUAL_OVERRIDE"
            is_manual_override = True
            classified = {
                "Dominio": ov.get("Dominio", ""),
                "Categoria": ov.get("Categoria", ""),
                "Subcategoria": ov.get("Subcategoria", ""),
                "TitularGasto": ov.get("TitularGasto", "MARLON"),
                "NaturalezaFinanciera": ov.get("NaturalezaFinanciera", "EGRESO_CONSUMO"),
                "ConfianzaClasificacion": "MANUAL_OVERRIDE",
                "PendienteRevision": 0,
                "EsPresupuestable": int(ov.get("EsPresupuestable", 1)),
                "EsConsumoPersonal": int(ov.get("EsConsumoPersonal", 1)),
                "EsIngresoEconomico": int(ov.get("EsIngresoEconomico", 0)),
                "EsEgresoEconomico": int(ov.get("EsEgresoEconomico", 1)),
                "EsNegocio": int(ov.get("EsNegocio", 0)),
                "EsAhorro": int(ov.get("EsAhorro", 0)),
                "EsPrestamo": int(ov.get("EsPrestamo", 0)),
                "EsDeuda": int(ov.get("EsDeuda", 0)),
                "EsTransferencia": int(ov.get("EsTransferencia", 0)),
                "EsReembolso": int(ov.get("EsReembolso", 0)),
            }

        # 2. Rule evaluation (if no manual override)
        if classified is None and not df_rules.empty:
            for _, rule in df_rules.iterrows():
                r_tipo = str(rule.get("TipoRial", "")).strip()
                r_cat = str(rule.get("CategoriaRial", "")).strip()
                r_subcat = str(rule.get("SubcategoriaRial", "")).strip()
                r_pat = str(rule.get("PatternDescripcion", "")).strip()
                r_prio = rule.get("Priority", 99)

                if r_tipo and r_tipo.lower() != tipo_rial.lower():
                    continue
                if r_cat and r_cat.lower() != cat_rial.lower():
                    continue
                if r_subcat and r_subcat.lower() != subcat_rial.lower():
                    continue
                if r_pat:
                    try:
                        if not re.search(r_pat, desc, re.IGNORECASE):
                            continue
                    except Exception:
                        continue

                regla_id = str(rule.get("RuleId", "R_RULE")).strip()
                confianza = "HIGH" if r_prio <= 25 else "MEDIUM"
                classified = {
                    "Dominio": str(rule.get("Dominio", "")).strip(),
                    "Categoria": str(rule.get("Categoria", "")).strip(),
                    "Subcategoria": str(rule.get("Subcategoria", "")).strip(),
                    "TitularGasto": str(rule.get("TitularGasto", "")).strip() or "MARLON",
                    "NaturalezaFinanciera": str(rule.get("NaturalezaFinanciera", "")).strip() or "EGRESO_CONSUMO",
                    "ConfianzaClasificacion": confianza,
                    "PendienteRevision": 0,
                    "EsPresupuestable": int(rule.get("EsPresupuestable", 1) or 0),
                    "EsConsumoPersonal": int(rule.get("EsConsumoPersonal", 1) or 0),
                    "EsIngresoEconomico": int(rule.get("EsIngresoEconomico", 0) or 0),
                    "EsEgresoEconomico": int(rule.get("EsEgresoEconomico", 1) or 0),
                    "EsNegocio": int(rule.get("EsNegocio", 0) or 0),
                    "EsAhorro": int(rule.get("EsAhorro", 0) or 0),
                    "EsPrestamo": int(rule.get("EsPrestamo", 0) or 0),
                    "EsDeuda": int(rule.get("EsDeuda", 0) or 0),
                    "EsTransferencia": int(rule.get("EsTransferencia", 0) or 0),
                    "EsReembolso": int(rule.get("EsReembolso", 0) or 0),
                }
                break

        # Check for YUMMY without sufficient context -> Force UNCLASSIFIED (ONLY if not a manual override)
        if not is_manual_override and re.search(r"(?i)yummy|yumy", desc):
            context_keywords = r"(?i)traslado|trabajo|pasaje|casa\b|metropolis|guayos|ag[uú]itas|firestone|honda|canaima|premiados|kit|entrega|cliente|comida|restaurante|donas|perro|hamburguesa|pizza|anilet|cashea"
            if not re.search(context_keywords, desc):
                regla_id = "UNCLASSIFIED_YUMMY_NO_CONTEXT"
                classified = None

        # 3. Fallback PENDIENTE_CLASIFICAR
        if classified is None:
            regla_id = regla_id or "UNCLASSIFIED_FALLBACK"
            classified = {
                "Dominio": "CONTROL",
                "Categoria": "Pendiente clasificar",
                "Subcategoria": "Revisión manual",
                "TitularGasto": "NO_APLICA",
                "NaturalezaFinanciera": "UNCLASSIFIED",
                "ConfianzaClasificacion": "UNCLASSIFIED",
                "PendienteRevision": 1,
                "EsPresupuestable": 0,
                "EsConsumoPersonal": 0,
                "EsIngresoEconomico": 1 if tipo_rial == "Ingreso" else 0,
                "EsEgresoEconomico": 1 if tipo_rial == "Egreso" else 0,
                "EsNegocio": 0,
                "EsAhorro": 0,
                "EsPrestamo": 0,
                "EsDeuda": 0,
                "EsTransferencia": 1 if "Transferencia" in tipo_rial else 0,
                "EsReembolso": 0,
            }

        # Enforce strict financial semantics
        if classified["EsTransferencia"] == 1 or "Transferencia" in tipo_rial:
            classified["Dominio"] = "PATRIMONIAL"
            classified["Categoria"] = "Transferencias"
            classified["EsIngresoEconomico"] = 0
            classified["EsEgresoEconomico"] = 0
            classified["EsConsumoPersonal"] = 0

        if classified["Subcategoria"] in ["Préstamo otorgado", "Préstamo recibido"] or cat_rial in ["Préstamo otorgado", "Préstamo recibido"]:
            classified["Dominio"] = "PATRIMONIAL"
            classified["Categoria"] = "Préstamos"
            classified["EsIngresoEconomico"] = 0
            classified["EsEgresoEconomico"] = 0
            classified["EsConsumoPersonal"] = 0
            classified["EsPrestamo"] = 1

        if classified["Subcategoria"] == "Saldo inicial / ahorro previo" or "saldo inicial" in desc.lower():
            classified["Dominio"] = "PATRIMONIAL"
            classified["Categoria"] = "Ahorro"
            classified["EsIngresoEconomico"] = 0
            classified["EsEgresoEconomico"] = 0
            classified["EsConsumoPersonal"] = 0
            classified["EsAhorro"] = 1

        if classified["Dominio"] == "NEGOCIO" or classified["Categoria"] == "PremiadosVE":
            classified["Dominio"] = "NEGOCIO"
            classified["EsNegocio"] = 1
            classified["EsConsumoPersonal"] = 0

        if classified["Categoria"] == "Deuda / CASHEA":
            if classified["Subcategoria"] == "Cuota existente":
                classified["Dominio"] = "PERSONAL"
                classified["NaturalezaFinanciera"] = "PAGO_DEUDA"
                classified["EsDeuda"] = 1
                classified["EsConsumoPersonal"] = 0
                classified["EsPresupuestable"] = 1
                classified["EsEgresoEconomico"] = 1
            elif classified["Subcategoria"] == "Nueva compra / Inicial":
                classified["Dominio"] = "PERSONAL"
                classified["NaturalezaFinanciera"] = "EGRESO_CONSUMO"
                classified["EsDeuda"] = 1
                classified["EsConsumoPersonal"] = 1
                classified["EsPresupuestable"] = 1
                classified["EsEgresoEconomico"] = 1

        classified["ReglaClasificacion"] = regla_id
        merged_row = {**r.to_dict(), **classified}
        classified_rows.append(merged_row)

    df_result = pd.DataFrame(classified_rows)

    exact_mask = df_result.duplicated(subset=['Fecha', 'Hora', 'TipoRial', 'Cuenta', 'MontoOriginal', 'MonedaOriginal', 'DescripcionOriginal', 'CategoriaRial'], keep=False)
    possible_mask = df_result.duplicated(subset=['Fecha', 'TipoRial', 'MontoOriginal', 'MonedaOriginal'], keep=False) & (~exact_mask)

    df_result["DuplicateType"] = "NONE"
    df_result.loc[exact_mask, "DuplicateType"] = "EXACT_DUPLICATE"
    df_result.loc[possible_mask, "DuplicateType"] = "POSSIBLE_DUPLICATE"
    df_result["PosibleDuplicado"] = df_result["DuplicateType"].apply(lambda x: 1 if x != "NONE" else 0)

    return df_result
