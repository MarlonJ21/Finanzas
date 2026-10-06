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

        # 2. Special system transfers
        if classified is None and ("Transferencia" in tipo_rial):
            regla_id = "R_TRANSFERENCIA"
            sub = "Transferencia interna salida" if "salida" in tipo_rial.lower() else "Transferencia interna entrada"
            classified = {
                "Dominio": "PATRIMONIAL",
                "Categoria": "Transferencias",
                "Subcategoria": subcat_rial or sub,
                "TitularGasto": "NO_APLICA",
                "NaturalezaFinanciera": "TRANSFERENCIA_INTERNA",
                "ConfianzaClasificacion": "HIGH",
                "PendienteRevision": 0,
                "EsPresupuestable": 0,
                "EsConsumoPersonal": 0,
                "EsIngresoEconomico": 0,
                "EsEgresoEconomico": 0,
                "EsNegocio": 0,
                "EsAhorro": 0,
                "EsPrestamo": 0,
                "EsDeuda": 0,
                "EsTransferencia": 1,
                "EsReembolso": 0,
            }

        # 3. Native RIAL Passthrough (Option 3: Single Source of Truth)
        # If user registered a Categoria in RIAL, we respect it directly (1:1)
        if classified is None and cat_rial:
            regla_id = "RIAL_NATIVE"
            cat_clean = cat_rial.strip()
            subcat_clean = subcat_rial.strip() if subcat_rial.strip() else cat_clean

            # Dominio & Financial Flags
            is_cxc = 1 if (
                ("cuenta" in cat_clean.lower() and "cobrar" in cat_clean.lower()) or
                "cxc" in cat_clean.lower() or "cxc" in desc.lower() or
                "cobro de deuda" in cat_clean.lower() or "cobro de deuda" in desc.lower()
            ) else 0

            is_prestamo = 1 if (
                cat_clean.lower() in ["préstamo otorgado", "préstamo recibido", "prestamo otorgado", "prestamo recibido", "préstamos", "prestamos"] or
                "prestamo" in desc.lower() or "préstamo" in desc.lower()
            ) else 0

            is_ahorro = 1 if (
                cat_clean.lower() in ["ahorro", "ahorros"] or
                "saldo inicial" in desc.lower()
            ) else 0

            is_negocio = 1 if (
                cat_clean.lower() in ["premiadosve", "gastos premiadosve", "ventas"] or
                "premiados" in cat_clean.lower() or
                "premiados" in desc.lower() or
                "meta ads" in desc.lower()
            ) else 0

            is_cashea = 1 if (
                cat_clean.upper() in ["CASHEA", "DEUDA / CASHEA"] or
                "cashea" in desc.lower() or
                "cuota" in desc.lower() or
                cat_clean.lower() in ["pago de deuda", "deuda"]
            ) else 0

            # Normalize canonical category for Business and Cashea
            if is_negocio:
                dominio = "NEGOCIO"
                titular = "PREMIADOSVE"
                cat_clean = "PremiadosVE"
                if tipo_rial == "Ingreso":
                    nat = "VENTAS"
                    es_ing, es_egr, es_presup, es_cons = 1, 0, 0, 0
                    if not subcat_rial or subcat_clean == "Ventas":
                        subcat_clean = "Ventas"
                else:
                    nat = "EGRESO_OPERATIVO"
                    es_ing, es_egr, es_presup, es_cons = 0, 1, 1, 0
                    if "meta ads" in desc.lower() or "publicidad" in desc.lower() or subcat_clean.lower() in ["meta ads", "meta ads / publicidad"]:
                        subcat_clean = "Meta Ads"
            elif is_cxc or is_prestamo:
                dominio = "PATRIMONIAL"
                titular = "MARLON"
                nat = "CUENTA_POR_COBRAR" if is_cxc else "PRESTAMO"
                es_ing, es_egr, es_presup, es_cons = 0, 0, 0, 0
                if is_cxc:
                    cat_clean = "Cuentas por cobrar"
                    subcat_clean = "Cobro CxC"
            elif is_ahorro:
                dominio = "PATRIMONIAL"
                titular = "MARLON"
                nat = "AHORRO"
                cat_clean = "Ahorro"
                es_ing, es_egr, es_presup, es_cons = 0, 0, 0, 0
            elif is_cashea:
                dominio = "PERSONAL"
                titular = "MARLON"
                nat = "PAGO_DEUDA"
                cat_clean = "Deuda / CASHEA"
                es_ing, es_egr, es_presup = 0, 1, 1
                is_cuota = "cuota" in desc.lower() or "cuota" in subcat_clean.lower() or not subcat_rial
                es_cons = 0 if is_cuota else 1
                if not subcat_rial:
                    subcat_clean = "Cuota existente"
            elif cat_clean.lower() in ["salario", "otros ingresos", "ingresos"] or tipo_rial == "Ingreso":
                dominio = "PERSONAL"
                titular = "MARLON"
                nat = "INGRESOS_OPERATIVOS"
                es_ing, es_egr, es_presup, es_cons = 1, 0, 0, 0
            else:
                dominio = "PERSONAL"
                titular = "MARLON"
                nat = "EGRESO_CONSUMO"
                es_ing, es_egr, es_presup, es_cons = 0, 1, 1, 1

            classified = {
                "Dominio": dominio,
                "Categoria": cat_clean,
                "Subcategoria": subcat_clean,
                "TitularGasto": titular,
                "NaturalezaFinanciera": nat,
                "ConfianzaClasificacion": "HIGH",
                "PendienteRevision": 0,
                "EsPresupuestable": es_presup,
                "EsConsumoPersonal": es_cons,
                "EsIngresoEconomico": es_ing,
                "EsEgresoEconomico": es_egr,
                "EsNegocio": is_negocio,
                "EsAhorro": is_ahorro,
                "EsPrestamo": is_prestamo,
                "EsDeuda": is_cashea,
                "EsTransferencia": 0,
                "EsReembolso": 0,
            }

        # 4. Fallback to category_rules.csv only when RIAL Categoria is missing/empty
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

        # 5. Fallback PENDIENTE_CLASIFICAR
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
