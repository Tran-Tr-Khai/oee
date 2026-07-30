from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path
from typing import Callable

import pandas as pd


SheetExtractorFunc = Callable[[pd.ExcelFile, str], pd.DataFrame]


class LoadStrategy(StrEnum):
    APPEND = "append"
    REPLACE = "replace"


class IncrementalType(StrEnum):
    BIGINT = "bigint"
    TIMESTAMP = "timestamp"


@dataclass(frozen=True)
class PipelineConfig:
    table_name: str
    file_pattern: str = ""
    extractor_func: SheetExtractorFunc | None = None
    load_strategy: LoadStrategy = LoadStrategy.REPLACE
    incremental_column: str = ""
    incremental_type: IncrementalType = IncrementalType.TIMESTAMP
    sort_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class MssqlConfig:
    server: str
    database: str
    username: str
    password: str
    driver: str = "ODBC Driver 17 for SQL Server"
    trust_server_certificate: bool = True


ROOT_DIR = Path(__file__).resolve().parents[3]

DATA_DIR = ROOT_DIR / "data" / "raw"
DB_DIR = ROOT_DIR / "db"
LOG_DIR = ROOT_DIR / "logs"

DUCKDB_PATH = DB_DIR / "oee.db"
ENV_PATH = ROOT_DIR / ".env"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", maxsplit=1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def get_mssql_config() -> MssqlConfig:
    def require(name: str) -> str:
        value = os.getenv(name)
        if value:
            return value
        raise ValueError(f"Missing required environment variable: {name}")

    return MssqlConfig(
        server=require("MSSQL_SERVER"),
        database=require("MSSQL_DATABASE"),
        username=require("MSSQL_USERNAME"),
        password=require("MSSQL_PASSWORD"),
        driver=os.getenv(
            "MSSQL_DRIVER",
            "ODBC Driver 17 for SQL Server",
        ),
        trust_server_certificate=os.getenv(
            "MSSQL_TRUST_SERVER_CERTIFICATE",
            "true",
        ).strip().lower() in {"1", "true", "yes", "y", "on"},
    )


load_env_file(ENV_PATH)
