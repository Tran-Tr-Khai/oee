from datetime import datetime, timezone
import logging
from pathlib import Path

import duckdb
import pandas as pd

from oee_ingestion.config import PipelineConfig, LOG_DIR

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "ingest_pipeline.log"),
        logging.StreamHandler(),
    ],
)

METADATA_COLS = [
    "_source_file", 
    "_sheet_name", 
    "_row_number", 
    "_ingested_at"
]

def add_metadata(df: pd.DataFrame, excel_file: Path, sheet_name: str) -> pd.DataFrame:
    df = df.copy()
    df["_source_file"] = excel_file
    df["_sheet_name"] = sheet_name
    df["_row_number"] = range(1, len(df) + 1)
    df["_ingested_at"] = datetime.now(timezone.utc)
    return df

def quote_identifier(identifier: str) -> str:
    """Quote an SQL identifier safely for DuckDB."""
    return '"' + identifier.replace('"', '""') + '"'


def run_ingest_pipeline(
    conn: duckdb.DuckDBPyConnection,
    data_dir: Path,
    config: PipelineConfig
) -> None:
    excel_files = sorted(
        [
            path
            for path in [
                *data_dir.rglob(f"{config.file_pattern}.xlsx"),
                *data_dir.rglob(f"{config.file_pattern}.xls"),
            ]
            if not path.name.startswith("~$")
        ],
        key=lambda path: str(path).lower(),
    )
    if not excel_files:
        logging.warning("No files found for pattern: %s", config.file_pattern)
        return

    frames: list[pd.DataFrame] = []
    union_schema: dict[str, None] = {}

    for file_idx, excel_file in enumerate(excel_files, start=1):
        logging.info(
            "[%d/%d] Reading: %s",
            file_idx,
            len(excel_files),
            excel_file.name,
        )

        try:
            # Context manager đảm bảo workbook được đóng ngay sau khi xử lý.
            with pd.ExcelFile(excel_file) as workbook:
                for sheet_name in workbook.sheet_names:
                    try:
                        df = config.extractor_func(workbook, sheet_name)
                    except Exception:
                        logging.exception(f"Failed extracting file={excel_file.name}, sheet={sheet_name}")
                        raise

                    if df.empty:
                        continue

                    df = add_metadata(df, excel_file, sheet_name)
                    for col in df.columns:
                        union_schema.setdefault(col, None)
                    frames.append(df)
        except Exception:
            logging.exception("Failed reading workbook: %s", excel_file)
            raise

    if not frames:
        logging.warning("No valid data found to ingest for %s", config.table_name)
        return

    # Giữ cách ingest theo batch của bản gốc: ít RAM hơn pd.concat toàn bộ dữ liệu.
    target_columns = list(union_schema)
    quoted_table = quote_identifier(config.table_name)
    select_sql = ",\n".join(
        f"CAST({quote_identifier(col)} AS VARCHAR) AS {quote_identifier(col)}"
        for col in target_columns
    )

    conn.execute(f"DROP TABLE IF EXISTS {quoted_table}")
    total_rows = 0
    is_first_batch = True

    try:
        for df in frames:
            aligned_df = df.reindex(columns=target_columns).astype("string")
            conn.register("temp_df", aligned_df)
            try:
                if is_first_batch:
                    conn.execute(
                        f"CREATE TABLE {quoted_table} AS "
                        f"SELECT {select_sql} FROM temp_df"
                    )
                    is_first_batch = False
                else:
                    # Nêu rõ cột đích để tránh phụ thuộc ngầm vào thứ tự schema.
                    quoted_columns = ", ".join(
                        quote_identifier(col) for col in target_columns
                    )
                    conn.execute(
                        f"INSERT INTO {quoted_table} ({quoted_columns}) "
                        f"SELECT {quoted_columns} FROM temp_df"
                    )
            finally:
                conn.unregister("temp_df")

            total_rows += len(aligned_df)
    except Exception:
        conn.execute(f"DROP TABLE IF EXISTS {quoted_table}")
        raise

    logging.info(f"Finished ingesting {total_rows:,} rows into {config.table_name}")