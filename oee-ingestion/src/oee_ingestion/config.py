from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

import pandas as pd


SheetExtractorFunc = Callable[[pd.ExcelFile, str], pd.DataFrame]


class LoadStrategy(StrEnum):
    REPLACE = "replace"
    UPSERT = "upsert"


@dataclass(frozen=True)
class PipelineConfig:
    table_name: str
    file_pattern: str
    extractor_func: SheetExtractorFunc
    load_strategy: LoadStrategy = LoadStrategy.REPLACE
    merge_keys: tuple[str, ...] = ()


ROOT_DIR = Path(__file__).resolve().parents[3]

DATA_DIR = ROOT_DIR / "data"
DB_DIR = ROOT_DIR / "db"
LOG_DIR = ROOT_DIR / "logs"

DUCKDB_PATH = DB_DIR / "oee.db"
