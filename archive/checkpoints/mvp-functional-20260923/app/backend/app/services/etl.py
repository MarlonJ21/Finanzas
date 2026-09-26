from __future__ import annotations

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
    return subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "pandas",
            "--with",
            "pyarrow",
            "--with",
            "numpy",
            "python",
            "src/main.py",
        ],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def build_staging_workspace(csv_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    staging = TEMP_IMPORT_DIR / f"staging_{timestamp}"
    staging.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC_DIR, staging / "src")
    shutil.copytree(CONFIG_DIR, staging / "config")
    (staging / "raw").mkdir()
    (staging / "output").mkdir()
    shutil.copy2(csv_path, staging / "raw" / "rial-movimientos_2000-01-01_a_2100-12-31.csv")
    return staging


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
    staging = build_staging_workspace(csv_path)
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
        "transaction_rows": summary.get("transaction_rows", 0),
        "summary_rows": max(base["physical_rows"] - summary.get("transaction_rows", 0) - 1, 0),
        "min_date": None,
        "max_date": summary.get("cut_date"),
        "cut_date": summary.get("cut_date"),
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
        shutil.copy2(commit_source, RAW_DIR / "rial-movimientos_2000-01-01_a_2100-12-31.csv")

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
