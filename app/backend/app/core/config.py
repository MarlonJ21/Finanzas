from __future__ import annotations

import os
from pathlib import Path


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src" / "main.py").exists() and (parent / "output").exists():
            return parent
    env_root = os.getenv("DWH_PROJECT_ROOT")
    if env_root:
        return Path(env_root).resolve()
    raise RuntimeError("Could not locate DWH project root")


PROJECT_ROOT = find_project_root()
SRC_DIR = PROJECT_ROOT / "src"
RAW_DIR = PROJECT_ROOT / "raw"
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "output"
ARCHIVE_RIAL_DIR = PROJECT_ROOT / "archive" / "rial"
APP_DATA_DIR = PROJECT_ROOT / "app" / "data"
APP_DB_PATH = APP_DATA_DIR / "app.db"
TEMP_IMPORT_DIR = PROJECT_ROOT / "app" / "data" / "imports"

APP_VERSION = "0.1.0"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
