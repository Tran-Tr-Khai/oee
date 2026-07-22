from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from typing import Any, Callable

import duckdb
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# -----------------------------
# Configuration & Constants
# -----------------------------
METADATA_COLS = ["_source_file", "_sheet_name", "_row_number", "_ingested_at"]

CLEAN_CHARS_REGEX = re.compile(r"[()]+")
SPLIT_CHARS_REGEX = re.compile(r"[\s/\\\-.]+")
MULTIPLE_UNDERSCORES_REGEX = re.compile(r"_+")
KOREAN_DATE_REGEX = re.compile(r"(\d{1,2})월(\d{1,2})일")
TEXTILE_CURRENT_MONTH_START_COL_IDX = 5

START_BEAM_COLUMN_MAP = {
    "호기_số_máy": "machine_no",
    "model": "model",
    "품목_loại_hàng": "item_type",
    "unit": "unit",
    "상대일_ngày_lên_beam": "beam_start_date",
    "po": "po",
    "order": "order_no",
    "lot_no": "lot_no",
    "total_yarn": "total_yarn",
    "b_m_no": "beam_no",
    "length": "length",
    "pro": "planned_output",
    "대차_chênh_lệch": "output_gap",
    "%": "output_rate",
    "하대예정일_ngày_dự_kiến_hết_beam": "expected_beam_end_at",
    "제직기간일_thời_gian_dệt": "weaving_days",
    "1일생산량mts_số_mts_dệt_mỗi_ngày": "daily_output_mts",
}

START_BEAM_DATE_COLS = ["beam_start_date", "expected_beam_end_at"]
START_BEAM_NUMERIC_COLS = [
    "machine_no",
    "total_yarn",
    "length",
    "planned_output",
    "output_gap",
    "output_rate",
    "weaving_days",
    "daily_output_mts",
]

# Định nghĩa kiểu hàm để tái sử dụng (Strategy Pattern)
SheetExtractorFunc = Callable[[pd.ExcelFile, str], pd.DataFrame]


# -----------------------------
# Core: Column Normalization
# -----------------------------
def normalize_column_name(column: Any) -> str:
    if isinstance(column, tuple):
        parts = [
            str(raw).strip()
            for raw in column
            if pd.notna(raw)
            and str(raw).strip()
            and not str(raw).startswith("Unnamed")
        ]
        name = "_".join(parts)
    else:
        name = str(column).strip()

    name = CLEAN_CHARS_REGEX.sub("", name.lower())
    name = SPLIT_CHARS_REGEX.sub("_", name)
    name = MULTIPLE_UNDERSCORES_REGEX.sub("_", name)
    return name.strip("_")

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = []
    seen: dict[str, int] = {}

    for col in df.columns:
        name = normalize_column_name(col)
        if not name: 
            name = "unnamed"
    
        count = seen.get(name, 0)
        seen[name] = count + 1
        columns.append(name if count == 0 else f"{name}_{count + 1}")
    
    df.columns = columns
    return df

def normalize_machine_no(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .replace("", pd.NA)
    )

def resolve_production_year(sheet_year: int, sheet_month: int, production_month: int, ) -> int:
    month_difference = production_month - sheet_month

    if month_difference >= 6:
        return sheet_year - 1

    if month_difference <= -6:
        return sheet_year + 1

    return sheet_year

def normalize_textile_merge_keys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["machine_no"] = normalize_machine_no(df["machine_no"])
    df["prod_date"] = pd.to_datetime(
        df["prod_date"],
        errors="coerce",
    )

    return df.dropna(subset=["machine_no", "prod_date"],)


# -----------------------------
# Extractors
# -----------------------------
def extract_complete_beam(workbook: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(workbook, sheet_name=sheet_name, header=[0, 1])
    df = normalize_columns(df)
    return df.dropna(axis=0, how="all").dropna(axis=1, how="all")

def extract_start_beam(workbook: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    raw_head = pd.read_excel(workbook, sheet_name=sheet_name, header=None, nrows=3)
    if raw_head.empty:
        return pd.DataFrame()

    updated_at = None
    for _, row in raw_head.iterrows():
        dates = pd.to_datetime(row.dropna(), errors="coerce").dropna()
        if not dates.empty:
            updated_at = dates.iloc[-1]
            break

    df = pd.read_excel(workbook, sheet_name=sheet_name, header=2)
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

    if df.empty:
        return pd.DataFrame()

    df = normalize_columns(df).rename(columns=START_BEAM_COLUMN_MAP)
    df["_updated_at"] = updated_at
    df["_excel_row_number"] = df.index + 4

    for col in START_BEAM_DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in START_BEAM_NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.reset_index(drop=True)

def extract_textile_days(workbook: pd.ExcelFile, sheet_name: str,) -> pd.DataFrame:
    sheet_key = sheet_name.strip().lower()
    if sheet_key.startswith("total") or sheet_key == "kangatang":
        return pd.DataFrame()

    df = pd.read_excel(workbook, sheet_name=sheet_name, header=None)

    if len(df) < 5:
        logging.warning(f"Skipping sheet {sheet_name}: expected at least 5 rows, found {len(df)}")
        return pd.DataFrame()

    production_headers = df.iloc[2].values
    lot_headers = df.iloc[3].values

    data_start_idx = 4
    machine_col_idx = 0

    # =========================================================
    # 1. Bóc tách dữ liệu LOT
    # =========================================================

    lot_cols: list[int] = []
    lot_dates: list[pd.Timestamp] = []

    sheet_year: int | None = None
    sheet_month:int | None = None

    for col_idx, value in enumerate(lot_headers):
        if pd.isna(value):
            continue

        lot_date = pd.to_datetime(value, errors="coerce")

        if pd.isna(lot_date):
            continue

        lot_cols.append(col_idx)
        lot_dates.append(lot_date)

        if sheet_year is None and col_idx >= TEXTILE_CURRENT_MONTH_START_COL_IDX:
            sheet_year = lot_date.year
            sheet_month = lot_date.month

    if not lot_cols:
        logging.warning(f"Skipping sheet {sheet_name}: no LOT date columns found")
        return pd.DataFrame()

    if sheet_year is None or sheet_month is None:
        logging.warning(
            f"Skipping sheet {sheet_name}: no current-month LOT date found "
            f"from column {TEXTILE_CURRENT_MONTH_START_COL_IDX} onwards"
        )
        return pd.DataFrame()
    
    df_lot = df.iloc[data_start_idx:, [machine_col_idx, *lot_cols]].copy()
    df_lot.columns = ["machine_no", *lot_dates]
    df_lot = df_lot.dropna(subset=["machine_no"])
    df_lot = df_lot.melt(id_vars=["machine_no"], var_name="prod_date", value_name="lot_no")
    df_lot["lot_no"] = df_lot["lot_no"].astype("string").str.strip().replace("", pd.NA)
    df_lot = df_lot.dropna(subset=["lot_no"])
    df_lot = normalize_textile_merge_keys(df_lot)

    if df_lot.empty:
        logging.warning(f"Skipping sheet {sheet_name}: LOT table is empty after cleaning")
        return pd.DataFrame()

    # =========================================================
    # 2. Bóc tách dữ liệu sản lượng
    # =========================================================
    source_rows = df.iloc[data_start_idx:]

    valid_machine_mask = source_rows.iloc[:, machine_col_idx].notna()
    valid_rows = source_rows.loc[valid_machine_mask]

    if valid_rows.empty:
        logging.warning(f"Skipping sheet {sheet_name}: no machine rows found")
        return pd.DataFrame()

    machines = normalize_machine_no(valid_rows.iloc[:, machine_col_idx]).to_numpy()
    prod_chunks: list[pd.DataFrame] = []

    for output_col_idx, header_value in enumerate(production_headers):
        header_text = "" if pd.isna(header_value) else str(header_value).replace(" ", "")

        if "생산량" not in header_text:
            continue

        if output_col_idx < 2:
            logging.warning(
                f"Skipping invalid production column {output_col_idx} "
                f"in sheet {sheet_name}"
            )
            continue

        meter_reading_col_idx = output_col_idx - 2
        cut_length_col_idx = output_col_idx - 1

        date_header = production_headers[meter_reading_col_idx]

        if isinstance(date_header, (pd.Timestamp, datetime)):
            production_month = date_header.month
            production_day = date_header.day

        else:
            date_text = (
                ""
                if pd.isna(date_header)
                else str(date_header).replace(" ", "")
            )

            date_match = KOREAN_DATE_REGEX.search(date_text)

            if not date_match:
                logging.warning(
                    f"Could not extract production date from "
                    f"{date_header} in sheet {sheet_name}, "
                    f"column {output_col_idx}"
                )
                continue

            production_month, production_day = map(int, date_match.groups())

        production_year = resolve_production_year(
            sheet_year=sheet_year,
            sheet_month=sheet_month,
            production_month=production_month,
        )

        try:
            prod_date = pd.Timestamp(
                year=production_year,
                month=production_month,
                day=production_day,
            )
        except ValueError:
            logging.warning(
                f"Skipping invalid production date {date_text} "
                f"in sheet {sheet_name}"
            )
            continue

        prod_chunks.append(
            pd.DataFrame({
                "machine_no": machines,
                "prod_date": prod_date,
                "meter_reading_m": valid_rows.iloc[:, meter_reading_col_idx].to_numpy(),
                "cut_length_m": valid_rows.iloc[:, cut_length_col_idx].to_numpy(),
                "prod_output_m": valid_rows.iloc[:, output_col_idx].to_numpy(),
            })
        )

    if not prod_chunks:
        logging.warning(f"Skipping sheet {sheet_name}: no production columns found")
        return pd.DataFrame()

    df_prod = pd.concat(prod_chunks, ignore_index=True)
    df_prod = normalize_textile_merge_keys(df_prod)
    if df_prod.empty:
        logging.warning(f"Skipping sheet {sheet_name}: production table is empty after cleaning")
        return pd.DataFrame()

    # =========================================================
    # 3. Ghép LOT với sản lượng
    # =========================================================

    df_final = pd.merge(
        df_lot,
        df_prod,
        on=["machine_no", "prod_date"],
        how="outer",
        validate="one_to_one",
    )

    df_final = df_final.dropna(
        subset=[
            "lot_no",
            "meter_reading_m",
            "cut_length_m",
            "prod_output_m",
        ],
        how="all",
    )

    numeric_cols = [
        "meter_reading_m",
        "cut_length_m",
        "prod_output_m",
    ]

    for col in numeric_cols:
        df_final[col] = pd.to_numeric(df_final[col], errors="coerce")

    df_final = df_final.sort_values(
        ["machine_no", "prod_date"],
        kind="stable",
    )

    return normalize_columns(df_final).reset_index(drop=True)

# -----------------------------
# Unified Pipeline Engine (Xử lý Ingest chung)
# -----------------------------
def add_metadata(df: pd.DataFrame, excel_file: Path, sheet_name: str) -> pd.DataFrame:
    df = df.copy()
    df["_source_file"] = excel_file.name
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
    table_name: str,
    file_pattern: str,
    extractor_func: SheetExtractorFunc,
) -> None:
    # Sắp xếp để kết quả/schema ổn định giữa các lần chạy.
    excel_files = sorted(
        [
            path
            for path in [
                *data_dir.rglob(f"{file_pattern}.xlsx"),
                *data_dir.rglob(f"{file_pattern}.xls"),
            ]
            if not path.name.startswith("~$")
        ],
        key=lambda path: str(path).lower(),
    )
    if not excel_files:
        logging.warning("No files found for pattern: %s", file_pattern)
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
                        df = extractor_func(workbook, sheet_name)
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
        logging.warning("No valid data found to ingest for %s", table_name)
        return

    # Giữ cách ingest theo batch của bản gốc: ít RAM hơn pd.concat toàn bộ dữ liệu.
    target_columns = list(union_schema)
    quoted_table = quote_identifier(table_name)
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

    logging.info(f"Finished ingesting {total_rows:,} rows into {table_name}")

# -----------------------------
# Execution Entry Point
# -----------------------------
if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[3]
    DATA_DIR = ROOT / "data"
    DUCKDB_PATH = ROOT / "db" / "oee.db"

    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    PIPELINES = {
        "complete_beam": {
            "table_name": "raw_complete_beam",
            "pattern": "*complete_beam*",
            "extractor": extract_complete_beam,
        },
        "start_beam": {
            "table_name": "raw_start_beam",
            "pattern": "*start_beam*",
            "extractor": extract_start_beam,
        },
        "textile_days": {
            "table_name": "raw_textile_days",
            "pattern": "*textile_days*",
            "extractor": extract_textile_days,
        },
    }

    with duckdb.connect(str(DUCKDB_PATH)) as db_conn:
        logging.info(">>> Successfully connected to DuckDB <<<")

        for pipe_id, config in PIPELINES.items():
            logging.info("--- Starting Pipeline: %s ---", pipe_id.upper())
            run_ingest_pipeline(
                conn=db_conn,
                data_dir=DATA_DIR,
                table_name=config["table_name"],
                file_pattern=config["pattern"],
                extractor_func=config["extractor"],
            )

        logging.info(">>> All Pipelines Completed Successfully <<<")