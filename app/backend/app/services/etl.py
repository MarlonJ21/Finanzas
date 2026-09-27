from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import (
    APP_DB_PATH,
    ARCHIVE_RIAL_DIR,
    CONFIG_DIR,
    MAX_UPLOAD_BYTES,
    OUTPUT_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    SRC_DIR,
    TEMP_IMPORT_DIR,
)


def ensure_operational_db() -> None:
    APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(APP_DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                physical_rows INTEGER NOT NULL,
                transaction_rows INTEGER NOT NULL,
                cut_date TEXT,
                status TEXT NOT NULL,
                exact_duplicates INTEGER DEFAULT 0,
                possible_duplicates INTEGER DEFAULT 0,
                missing_fx INTEGER DEFAULT 0,
                pending_classification INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0
            )
            """
        )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def already_imported(file_hash: str) -> bool:
    ensure_operational_db()
    with sqlite3.connect(APP_DB_PATH) as con:
        row = con.execute(
            "SELECT 1 FROM import_history WHERE file_hash=? AND status='PASS' LIMIT 1",
            [file_hash],
        ).fetchone()
    return row is not None


def insert_import_history(data: dict[str, Any]) -> None:
    ensure_operational_db()
    with sqlite3.connect(APP_DB_PATH) as con:
        con.execute(
            """
            INSERT INTO import_history (
              timestamp, filename, file_hash, file_size, physical_rows, transaction_rows,
              cut_date, status, exact_duplicates, possible_duplicates, missing_fx,
              pending_classification, duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                data["timestamp"],
                data["filename"],
                data["file_hash"],
                data["file_size"],
                data["physical_rows"],
                data["transaction_rows"],
                data.get("cut_date"),
                data["status"],
                data.get("exact_duplicates", 0),
                data.get("possible_duplicates", 0),
                data.get("missing_fx", 0),
                data.get("pending_classification", 0),
                data.get("duration_ms", 0),
            ],
        )


def validate_csv_file(path: Path, original_name: str) -> dict[str, Any]:
    if path.suffix.lower() != ".csv" and not original_name.lower().endswith(".csv"):
        raise ValueError("INVALID_EXTENSION")
    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise ValueError("FILE_TOO_LARGE")
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    header = next((line for line in lines if line.startswith("Fecha,")), "")
    required = ["Fecha", "Hora", "Tipo", "Categoría", "Descripción", "Cuenta", "Moneda"]
    missing = [col for col in required if col not in header]
    if missing:
        raise ValueError(f"INVALID_RIAL_COLUMNS:{','.join(missing)}")
    return {"file_size": size, "physical_rows": len(lines)}


def run_existing_pipeline(workspace: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    src_dir = (workspace / "src").resolve()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pp}" if existing_pp else str(src_dir)

    uv_bin = shutil.which("uv")
    if uv_bin:
        cmd = [
            uv_bin,
            "run",
            "--with",
            "pandas",
            "--with",
            "pyarrow",
            "--with",
            "numpy",
            "python",
            "src/main.py",
        ]
    else:
        cmd = [sys.executable, "src/main.py"]

    try:
        return subprocess.run(
            cmd,
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception as exc:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr=f"Error executing pipeline: {exc}",
        )


def parse_rial_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = None
        rows: list[dict[str, str]] = []
        for r in reader:
            if not r or not any(c.strip() for c in r):
                continue
            if header is None and r[0].strip() == "Fecha":
                header = [c.strip() for c in r]
                continue
            if r[0].strip() in ["Total ingresos", "Total egresos", "Balance"]:
                continue
            if header and len(r) >= len(header):
                rows.append({header[i]: r[i].strip() for i in range(len(header))})
    return header or [], rows


def prepare_merged_raw_file(incoming_csv: Path, target_path: Path) -> dict[str, Any]:
    incoming_header, incoming_rows = parse_rial_csv_rows(incoming_csv)
    if not incoming_rows:
        shutil.copy2(incoming_csv, target_path)
        return {
            "is_merged": False,
            "preserved_rows": 0,
            "incoming_rows": 0,
            "total_rows": 0,
            "min_date": None,
            "max_date": None,
            "incoming_period": "",
        }

    incoming_dates = [r["Fecha"] for r in incoming_rows if r.get("Fecha")]
    incoming_min = min(incoming_dates) if incoming_dates else ""
    incoming_max = max(incoming_dates) if incoming_dates else ""

    existing_file = current_raw_file()
    if not existing_file or not existing_file.exists():
        shutil.copy2(incoming_csv, target_path)
        return {
            "is_merged": False,
            "preserved_rows": 0,
            "incoming_rows": len(incoming_rows),
            "total_rows": len(incoming_rows),
            "min_date": incoming_min,
            "max_date": incoming_max,
            "incoming_period": f"{incoming_min} a {incoming_max}",
        }

    existing_header, existing_rows = parse_rial_csv_rows(existing_file)
    existing_dates = [r["Fecha"] for r in existing_rows if r.get("Fecha")]
    existing_min = min(existing_dates) if existing_dates else ""
    existing_max = max(existing_dates) if existing_dates else ""

    # If incoming covers whole existing history or broader, it is already a complete historical export
    if existing_min and incoming_min <= existing_min and incoming_max >= existing_max:
        shutil.copy2(incoming_csv, target_path)
        return {
            "is_merged": False,
            "preserved_rows": 0,
            "incoming_rows": len(incoming_rows),
            "total_rows": len(incoming_rows),
            "min_date": incoming_min,
            "max_date": incoming_max,
            "incoming_period": f"{incoming_min} a {incoming_max}",
        }

    # Partial / single month export: preserve all records outside incoming date range
    kept_rows = [r for r in existing_rows if r.get("Fecha", "") < incoming_min or r.get("Fecha", "") > incoming_max]
    merged_rows = kept_rows + incoming_rows
    merged_rows.sort(key=lambda r: (r.get("Fecha", ""), r.get("Hora", "")))

    header_to_use = existing_header if existing_header else incoming_header

    tot_ing = sum(float(r.get("Monto (USD)", 0) or 0) for r in merged_rows if r.get("Tipo") == "Ingreso")
    tot_egr = sum(float(r.get("Monto (USD)", 0) or 0) for r in merged_rows if r.get("Tipo") == "Egreso")
    bal = tot_ing - tot_egr

    with open(target_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header_to_use)
        writer.writeheader()
        writer.writerows(merged_rows)
        writer_raw = csv.writer(f)
        writer_raw.writerow([])
        writer_raw.writerow(["Total ingresos", f"{tot_ing:.2f}"])
        writer_raw.writerow(["Total egresos", f"{tot_egr:.2f}"])
        writer_raw.writerow(["Balance", f"{bal:.2f}"])

    all_dates = [r["Fecha"] for r in merged_rows if r.get("Fecha")]
    return {
        "is_merged": True,
        "preserved_rows": len(kept_rows),
        "incoming_rows": len(incoming_rows),
        "total_rows": len(merged_rows),
        "min_date": min(all_dates) if all_dates else incoming_min,
        "max_date": max(all_dates) if all_dates else incoming_max,
        "incoming_period": f"{incoming_min} a {incoming_max}",
    }


def build_staging_workspace(csv_path: Path) -> tuple[Path, dict[str, Any]]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    staging = TEMP_IMPORT_DIR / f"staging_{timestamp}"
    staging.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC_DIR, staging / "src")
    shutil.copytree(CONFIG_DIR, staging / "config")
    (staging / "raw").mkdir()
    (staging / "output").mkdir()
    target_raw = staging / "raw" / "rial-movimientos_2000-01-01_a_2100-12-31.csv"
    merge_info = prepare_merged_raw_file(csv_path, target_raw)
    return staging, merge_info


def summarize_output(output_dir: Path) -> dict[str, Any]:
    quality_path = output_dir / "calidad_datos.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
    presupuesto = pd.read_parquet(output_dir / "presupuesto.parquet")
    movimientos = pd.read_parquet(output_dir / "movimientos.parquet")
    return {
        "transaction_rows": int(len(movimientos)),
        "cut_date": str(movimientos["Fecha"].max()),
        "exact_duplicates": int(quality.get("exact_duplicates", 0)),
        "possible_duplicates": int(quality.get("possible_duplicates", 0)),
        "missing_fx": int(quality.get("missing_fx", 0)),
        "pending_classification": int(quality.get("unclassified", 0)),
        "planning_enabled": bool(not presupuesto.empty),
        "quality_status": quality.get("status"),
    }


def preview_import(csv_path: Path, original_name: str) -> dict[str, Any]:
    started = time.perf_counter()
    base = validate_csv_file(csv_path, original_name)
    file_hash = sha256_file(csv_path)
    staging, merge_info = build_staging_workspace(csv_path)
    result = run_existing_pipeline(staging)
    errors: list[str] = []
    warnings: list[str] = []
    status = "PASS"
    summary: dict[str, Any] = {}
    if result.returncode != 0:
        status = "FAIL"
        errors.append("ETL_PREVIEW_FAILED")
        errors.append(result.stderr[-2000:])
    else:
        summary = summarize_output(staging / "output")
        if summary.get("missing_fx", 0):
            warnings.append("MISSING_FX")
        if summary.get("pending_classification", 0):
            warnings.append("PENDING_CLASSIFICATION")
        if already_imported(file_hash):
            warnings.append("FILE_ALREADY_IMPORTED")
    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "filename": original_name,
        "file_hash": file_hash,
        "file_size": base["file_size"],
        "physical_rows": base["physical_rows"],
        "transaction_rows": summary.get("transaction_rows", merge_info.get("total_rows", 0)),
        "summary_rows": max(base["physical_rows"] - merge_info.get("incoming_rows", 0) - 1, 0),
        "min_date": merge_info.get("min_date"),
        "max_date": summary.get("cut_date") or merge_info.get("max_date"),
        "cut_date": summary.get("cut_date") or merge_info.get("max_date"),
        "is_merged": merge_info.get("is_merged", False),
        "preserved_rows": merge_info.get("preserved_rows", 0),
        "incoming_rows": merge_info.get("incoming_rows", 0),
        "incoming_period": merge_info.get("incoming_period", ""),
        "exact_duplicates": summary.get("exact_duplicates", 0),
        "possible_duplicates": summary.get("possible_duplicates", 0),
        "missing_fx": summary.get("missing_fx", 0),
        "pending_classification": summary.get("pending_classification", 0),
        "validation_status": status,
        "duration_ms": duration_ms,
        "errors": errors,
        "warnings": warnings,
        "staging_path": str(staging),
    }


def current_raw_file() -> Path | None:
    files = sorted(RAW_DIR.glob("*.csv"))
    return files[0] if files else None


def archive_current_raw() -> Path | None:
    raw = current_raw_file()
    if raw is None:
        return None
    ARCHIVE_RIAL_DIR.mkdir(parents=True, exist_ok=True)
    target = ARCHIVE_RIAL_DIR / f"rial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    shutil.copy2(raw, target)
    return target


def commit_import(csv_path: Path, original_name: str, force: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    preview = preview_import(csv_path, original_name)
    if preview["validation_status"] != "PASS":
        return {**preview, "commit_status": "FAIL", "rollback": True}
    if "FILE_ALREADY_IMPORTED" in preview["warnings"] and not force:
        return {**preview, "commit_status": "FAIL", "errors": ["FILE_ALREADY_IMPORTED"], "rollback": True}

    staging = Path(preview["staging_path"])
    merged_raw_source = staging / "raw" / "rial-movimientos_2000-01-01_a_2100-12-31.csv"
    commit_source = TEMP_IMPORT_DIR / f"commit_upload_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.csv"
    shutil.copy2(csv_path, commit_source)
    archive_path = archive_current_raw()
    previous_outputs = TEMP_IMPORT_DIR / f"rollback_outputs_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    if OUTPUT_DIR.exists():
        shutil.copytree(OUTPUT_DIR, previous_outputs)

    try:
        RAW_DIR.mkdir(exist_ok=True)
        for old in RAW_DIR.glob("*.csv"):
            old.unlink()
        # Copy the verified merged raw file to RAW_DIR and PROJECT_ROOT
        raw_target = RAW_DIR / "rial-movimientos_2000-01-01_a_2100-12-31.csv"
        shutil.copy2(merged_raw_source, raw_target)
        try:
            shutil.copy2(merged_raw_source, PROJECT_ROOT / "rial-movimientos_2000-01-01_a_2100-12-31.csv")
        except Exception:
            pass

        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        shutil.copytree(staging / "output", OUTPUT_DIR)
        duration_ms = int((time.perf_counter() - started) * 1000)
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filename": original_name,
            "file_hash": preview["file_hash"],
            "file_size": preview["file_size"],
            "physical_rows": preview["physical_rows"],
            "transaction_rows": preview["transaction_rows"],
            "cut_date": preview.get("cut_date"),
            "status": "PASS",
            "exact_duplicates": preview["exact_duplicates"],
            "possible_duplicates": preview["possible_duplicates"],
            "missing_fx": preview["missing_fx"],
            "pending_classification": preview["pending_classification"],
            "duration_ms": duration_ms,
        }
        insert_import_history(data)
        return {
            **preview,
            "duration_ms": duration_ms,
            "commit_status": "PASS",
            "archived_raw": str(archive_path) if archive_path else None,
            "rollback": False,
        }
    except Exception as exc:
        if previous_outputs.exists():
            if OUTPUT_DIR.exists():
                shutil.rmtree(OUTPUT_DIR)
            shutil.copytree(previous_outputs, OUTPUT_DIR)
        if archive_path and archive_path.exists():
            RAW_DIR.mkdir(exist_ok=True)
            if not any(RAW_DIR.glob("*.csv")):
                shutil.copy2(archive_path, RAW_DIR / "rial-movimientos_2000-01-01_a_2100-12-31.csv")
        return {**preview, "commit_status": "FAIL", "errors": [str(exc)], "rollback": True}
