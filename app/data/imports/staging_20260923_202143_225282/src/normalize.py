import csv
import hashlib
from typing import Tuple, List, Dict, Any
import pandas as pd
import numpy as np


def parse_float(val: Any) -> float:
    if val is None:
        return 0.0
    s = str(val).strip().replace(',', '')
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def generate_movimiento_id(row: Dict[str, str]) -> str:
    fields = [
        str(row.get('Fecha', '')).strip(),
        str(row.get('Hora', '')).strip(),
        str(row.get('Tipo', '')).strip(),
        str(row.get('Cuenta', '')).strip(),
        str(row.get('Moneda', '')).strip(),
        str(row.get('Monto (Bs)', '')).strip(),
        str(row.get('Monto (USD)', '')).strip(),
        str(row.get('Tu parte (Bs)', '')).strip(),
        str(row.get('Tu parte (USD)', '')).strip(),
        str(row.get('Descripción', '')).strip(),
        str(row.get('Categoría', '')).strip(),
    ]
    raw_str = "|".join(fields)
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()


def load_and_normalize_csv(csv_path: str) -> Tuple[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]:
    rows = []
    excluded_rows = []
    control_totals = {
        "raw_rows_total": 0,
        "summary_rows_count": 0,
        "transactions_count": 0,
        "control_total_ingresos": None,
        "control_total_egresos": None,
        "control_balance": None
    }

    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = None
        line_num = 0
        for row in reader:
            line_num += 1
            control_totals["raw_rows_total"] += 1
            
            # Check for header row
            if header is None and row and row[0].strip() == "Fecha":
                header = [c.strip() for c in row]
                excluded_rows.append({
                    "RowNumber": line_num,
                    "Tipo": "HEADER",
                    "Descripcion": ",".join(row[:4]),
                    "motivo_exclusion": "HEADER_ROW"
                })
                continue

            # Check for empty line
            if not row or not any(field.strip() for field in row):
                excluded_rows.append({
                    "RowNumber": line_num,
                    "Tipo": "EMPTY",
                    "Descripcion": "",
                    "motivo_exclusion": "EMPTY_LINE"
                })
                continue

            # Check for summary control rows at tail
            first_cell = row[0].strip()
            if first_cell in ["Total ingresos", "Total egresos", "Balance"]:
                control_totals["summary_rows_count"] += 1
                val = parse_float(row[1]) if len(row) > 1 else None
                if first_cell == "Total ingresos":
                    control_totals["control_total_ingresos"] = val
                elif first_cell == "Total egresos":
                    control_totals["control_total_egresos"] = val
                elif first_cell == "Balance":
                    control_totals["control_balance"] = val
                
                excluded_rows.append({
                    "RowNumber": line_num,
                    "Tipo": "SUMMARY_CONTROL",
                    "Descripcion": f"{first_cell}={val}",
                    "motivo_exclusion": "SUMMARY_CONTROL_ROW"
                })
                continue
            
            if header and len(row) >= len(header):
                row_dict = {header[i]: row[i].strip() for i in range(len(header))}
                rows.append(row_dict)

    control_totals["transactions_count"] = len(rows)

    normalized_data = []

    for r in rows:
        mov_id = generate_movimiento_id(r)
        fecha = r.get("Fecha", "").strip()
        hora = r.get("Hora", "").strip()
        fecha_hora = f"{fecha} {hora}".strip() if hora else fecha

        # Derive integer FechaKey YYYYMMDD and Quincena
        try:
            fecha_key = int(fecha.replace("-", ""))
            day_num = int(fecha.split("-")[2])
            quincena = 1 if day_num <= 15 else 2
        except Exception:
            fecha_key = None
            quincena = 1

        tipo_rial = r.get("Tipo", "").strip()
        categoria_rial = r.get("Categoría", "").strip()
        subcategoria_rial = r.get("Subcategoría", "").strip()
        descripcion_original = r.get("Descripción", "").strip()
        cuenta = r.get("Cuenta", "").strip()
        moneda_original = r.get("Moneda", "").strip().upper() or "VES"
        comprobante = r.get("Comprobante", "").strip()
        compartido = r.get("Compartido", "").strip()

        monto_bs = parse_float(r.get("Monto (Bs)"))
        monto_usd_raw = parse_float(r.get("Monto (USD)"))
        tu_parte_bs = parse_float(r.get("Tu parte (Bs)"))
        tu_parte_usd = parse_float(r.get("Tu parte (USD)"))
        tasa_registrada = parse_float(r.get("Tasa"))

        # Determine MontoOriginal
        if moneda_original == "VES":
            monto_original = tu_parte_bs if tu_parte_bs > 0 else monto_bs
        else:
            monto_original = tu_parte_usd if tu_parte_usd > 0 else monto_usd_raw

        # Precise MontoUSD calculation WITHOUT ANY IMPUTATION
        monto_usd = 0.0
        missing_fx = 0

        if moneda_original == "USD":
            monto_usd = monto_original
        elif tu_parte_usd > 0:
            monto_usd = tu_parte_usd
        elif monto_usd_raw > 0:
            monto_usd = monto_usd_raw
        elif moneda_original == "VES" and tasa_registrada > 0 and monto_original > 0:
            monto_usd = round(monto_original / tasa_registrada, 4)
        else:
            monto_usd = 0.0
            missing_fx = 1

        # Determine TasaImplicita ONLY when both amounts > 0
        tasa_implicita = None
        if moneda_original == "VES" and monto_original > 0 and monto_usd > 0:
            tasa_implicita = round(monto_original / monto_usd, 4)
        elif moneda_original == "USD" and monto_bs > 0 and monto_usd > 0:
            tasa_implicita = round(monto_bs / monto_usd, 4)

        norm_row = {
            "MovimientoId": mov_id,
            "FechaKey": fecha_key,
            "Fecha": fecha,
            "Hora": hora,
            "FechaHora": fecha_hora,
            "Quincena": quincena,
            "TipoRial": tipo_rial,
            "CategoriaRial": categoria_rial,
            "SubcategoriaRial": subcategoria_rial,
            "DescripcionOriginal": descripcion_original,
            "Cuenta": cuenta,
            "MonedaOriginal": moneda_original,
            "MontoOriginal": monto_original,
            "MontoUSD": monto_usd,
            "MontoBsRaw": monto_bs,
            "MontoUsdRaw": monto_usd_raw,
            "TuParteBs": tu_parte_bs,
            "TuParteUSD": tu_parte_usd,
            "TasaRegistrada": tasa_registrada if tasa_registrada > 0 else None,
            "TasaImplicita": tasa_implicita,
            "AnomaliaFX": missing_fx,
            "MissingFxRate": missing_fx,
            "Compartido": compartido,
            "Comprobante": comprobante
        }
        normalized_data.append(norm_row)

    df_norm = pd.DataFrame(normalized_data)
    control_totals["imputed_fx_values"] = 0
    return df_norm, control_totals, excluded_rows
