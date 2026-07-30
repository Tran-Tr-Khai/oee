from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path

import duckdb
import pandas as pd

from oee_ingestion.config import (
    IncrementalType,
    LOG_DIR,
    LoadStrategy,
    PipelineConfig,
)

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "ingest_pipeline.log"),
        logging.StreamHandler(),
    ],
)


def add_metadata(
    df: pd.DataFrame,
    excel_file: Path,
    sheet_name: str,
) -> pd.DataFrame:
    df = df.copy()
    df["_source_file"] = excel_file
    df["_sheet_name"] = sheet_name
    df["_row_number"] = range(1, len(df) + 1)
    df["_ingested_at"] = datetime.now(timezone.utc)
    return df


def quote_identifier(identifier: str) -> str:
    """Quote an SQL identifier safely for DuckDB."""
    return '"' + identifier.replace('"', '""') + '"'


def canonical_identifier(identifier: str) -> str:
    return identifier.casefold()


@contextmanager
def registered_frame(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    name: str = "temp_df",
) -> Iterator[str]:
    conn.register(name, df)
    try:
        yield name
    finally:
        conn.unregister(name)


def table_exists(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> bool:
    result = conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
        [table_name],
    ).fetchone()
    return result is not None


def get_table_columns(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchall()
    return [row[0] for row in rows]


def ensure_table_columns(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    incoming_columns: list[str],
) -> tuple[list[str], dict[str, str]]:
    existing_columns = get_table_columns(conn, table_name)
    existing_by_key = {
        canonical_identifier(column): column
        for column in existing_columns
    }
    missing_columns: list[str] = []

    quoted_table = quote_identifier(table_name)
    for column in incoming_columns:
        column_key = canonical_identifier(column)
        if column_key in existing_by_key:
            continue

        conn.execute(
            f"ALTER TABLE {quoted_table} "
            f"ADD COLUMN {quote_identifier(column)} VARCHAR"
        )
        existing_by_key[column_key] = column
        missing_columns.append(column)

    resolved_columns = {
        column: existing_by_key[canonical_identifier(column)]
        for column in incoming_columns
    }
    return [*existing_columns, *missing_columns], resolved_columns


def build_select_sql(columns: list[str]) -> str:
    return ",\n".join(
        f"CAST({quote_identifier(column)} AS VARCHAR) AS {quote_identifier(column)}"
        for column in columns
    )


def resolve_column_name(
    columns: list[str],
    column_name: str,
) -> str:
    columns_by_key = {
        canonical_identifier(column): column
        for column in columns
    }
    resolved_column = columns_by_key.get(
        canonical_identifier(column_name)
    )
    if resolved_column:
        return resolved_column

    raise ValueError(f"Missing column: {column_name}")


def sort_source_frame(
    df: pd.DataFrame,
    sort_columns: list[str],
) -> pd.DataFrame:
    sort_columns = [
        column
        for column in sort_columns
        if column in df.columns
    ]
    if not sort_columns:
        return df.reset_index(drop=True)

    return df.sort_values(
        by=sort_columns,
        kind="stable",
    ).reset_index(drop=True)


def get_incremental_select_sql(
    incremental_column: str,
    incremental_type: IncrementalType,
) -> str:
    quoted_column = quote_identifier(incremental_column)
    if incremental_type == IncrementalType.BIGINT:
        return f"SELECT MAX(TRY_CAST({quoted_column} AS BIGINT)) FROM"

    return f"SELECT MAX(TRY_CAST({quoted_column} AS TIMESTAMP)) FROM"


def get_latest_incremental_value(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    incremental_column: str,
    incremental_type: IncrementalType,
):
    return conn.execute(
        f"{get_incremental_select_sql(incremental_column, incremental_type)} "
        f"{quote_identifier(table_name)}"
    ).fetchone()[0]


def filter_incremental_rows(
    df: pd.DataFrame,
    incremental_column: str,
    incremental_type: IncrementalType,
    latest_value,
) -> pd.DataFrame:
    if latest_value is None:
        return df.reset_index(drop=True)

    if incremental_type == IncrementalType.BIGINT:
        values = pd.to_numeric(
            df[incremental_column],
            errors="coerce",
        )
    else:
        values = pd.to_datetime(
            df[incremental_column],
            errors="coerce",
        )

    return df.loc[values > latest_value].reset_index(drop=True)


def replace_table(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    frames: list[pd.DataFrame],
    target_columns: list[str],
) -> int:
    quoted_table = quote_identifier(table_name)
    quoted_columns = ", ".join(
        quote_identifier(column)
        for column in target_columns
    )

    conn.execute(f"DROP TABLE IF EXISTS {quoted_table}")

    total_rows = 0
    for frame_idx, df in enumerate(frames):
        aligned_df = df.reindex(columns=target_columns).astype("string")
        with registered_frame(conn, aligned_df) as relation_name:
            if frame_idx == 0:
                conn.execute(
                    f"CREATE TABLE {quoted_table} AS "
                    f"SELECT {build_select_sql(target_columns)} "
                    f"FROM {quote_identifier(relation_name)}"
                )
            else:
                conn.execute(
                    f"INSERT INTO {quoted_table} ({quoted_columns}) "
                    f"SELECT {quoted_columns} "
                    f"FROM {quote_identifier(relation_name)}"
                )

        total_rows += len(aligned_df)

    return total_rows


def append_table(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    frames: list[pd.DataFrame],
    target_columns: list[str],
    incremental_column: str,
    incremental_type: IncrementalType,
    sort_columns: list[str],
) -> int:
    source_df = pd.concat(frames, ignore_index=True)
    quoted_table = quote_identifier(table_name)
    source_sort_columns = [
        resolve_column_name(list(source_df.columns), column)
        for column in (
            list(sort_columns)
            if sort_columns
            else [incremental_column]
        )
    ]
    source_df = sort_source_frame(
        source_df,
        source_sort_columns,
    )

    if not table_exists(conn, table_name):
        aligned_df = source_df.reindex(columns=target_columns).astype("string")
        with registered_frame(conn, aligned_df) as relation_name:
            conn.execute(
                f"CREATE TABLE {quoted_table} AS "
                f"SELECT {build_select_sql(target_columns)} "
                f"FROM {quote_identifier(relation_name)}"
            )

        return len(source_df)

    target_columns, resolved_columns = ensure_table_columns(
        conn=conn,
        table_name=table_name,
        incoming_columns=target_columns,
    )
    source_df = source_df.rename(columns=resolved_columns)
    target_incremental_column = resolve_column_name(
        target_columns,
        resolved_columns.get(incremental_column, incremental_column),
    )
    target_sort_columns = [
        resolve_column_name(
            target_columns,
            resolved_columns.get(column, column),
        )
        for column in (
            list(sort_columns)
            if sort_columns
            else [incremental_column]
        )
    ]
    latest_value = get_latest_incremental_value(
        conn=conn,
        table_name=table_name,
        incremental_column=target_incremental_column,
        incremental_type=incremental_type,
    )
    source_df = sort_source_frame(
        source_df,
        target_sort_columns,
    )
    source_df = filter_incremental_rows(
        df=source_df,
        incremental_column=target_incremental_column,
        incremental_type=incremental_type,
        latest_value=latest_value,
    )
    if source_df.empty:
        return 0

    aligned_df = source_df.reindex(columns=target_columns).astype("string")
    insert_columns = ", ".join(
        quote_identifier(column)
        for column in target_columns
    )

    with registered_frame(conn, aligned_df) as relation_name:
        conn.execute(
            f"INSERT INTO {quoted_table} ({insert_columns}) "
            f"SELECT {insert_columns} "
            f"FROM {quote_identifier(relation_name)} AS source "
        )

    return len(aligned_df)


def run_dataframe_pipeline(
    conn: duckdb.DuckDBPyConnection,
    frames: list[pd.DataFrame],
    config: PipelineConfig,
) -> None:
    if not frames:
        logging.warning("No valid data found to ingest for %s", config.table_name)
        return

    target_columns: list[str] = []
    seen_columns: set[str] = set()
    for df in frames:
        for column in df.columns:
            if column in seen_columns:
                continue
            seen_columns.add(column)
            target_columns.append(column)

    try:
        if config.load_strategy == LoadStrategy.APPEND:
            if not config.incremental_column:
                raise ValueError(
                    f"Missing incremental_column for append pipeline: "
                    f"{config.table_name}"
                )
            total_rows = append_table(
                conn=conn,
                table_name=config.table_name,
                frames=frames,
                target_columns=target_columns,
                incremental_column=config.incremental_column,
                incremental_type=config.incremental_type,
                sort_columns=list(config.sort_columns),
            )
        else:
            total_rows = replace_table(
                conn=conn,
                table_name=config.table_name,
                frames=frames,
                target_columns=target_columns,
            )
    except Exception:
        if config.load_strategy == LoadStrategy.REPLACE:
            conn.execute(
                f"DROP TABLE IF EXISTS {quote_identifier(config.table_name)}"
            )
        raise

    logging.info(
        "Processed %s source rows into %s using %s mode",
        f"{total_rows:,}",
        config.table_name,
        config.load_strategy,
    )


def run_ingest_pipeline(
    conn: duckdb.DuckDBPyConnection,
    data_dir: Path,
    config: PipelineConfig,
) -> None:
    excel_files = sorted(
        [
            path
            for path in [
                *data_dir.glob(f"{config.file_pattern}.xlsx"),
                *data_dir.glob(f"{config.file_pattern}.xls"),
            ]
            if path.is_file() and not path.name.startswith("~$")
        ],
        key=lambda path: str(path).lower(),
    )
    if not excel_files:
        logging.warning("No files found for pattern: %s", config.file_pattern)
        return

    run_ingest_files(
        conn=conn,
        excel_files=excel_files,
        config=config,
    )


def run_ingest_files(
    conn: duckdb.DuckDBPyConnection,
    excel_files: list[Path],
    config: PipelineConfig,
) -> None:
    if config.extractor_func is None:
        raise ValueError(
            f"Missing extractor_func for Excel pipeline: {config.table_name}"
        )
    if not excel_files:
        logging.warning("No source files given for %s", config.table_name)
        return

    frames: list[pd.DataFrame] = []

    for file_idx, excel_file in enumerate(excel_files, start=1):
        if len(excel_files) == 1:
            logging.info(
                "Reading %s source file: %s",
                config.table_name,
                excel_file.name,
            )
        else:
            logging.info(
                "[%d/%d] Reading %s source file: %s",
                file_idx,
                len(excel_files),
                config.table_name,
                excel_file.name,
            )

        try:
            with pd.ExcelFile(excel_file) as workbook:
                for sheet_name in workbook.sheet_names:
                    try:
                        df = config.extractor_func(workbook, sheet_name)
                    except Exception:
                        logging.exception(
                            "Failed extracting file=%s, sheet=%s",
                            excel_file.name,
                            sheet_name,
                        )
                        raise

                    if df.empty:
                        continue

                    frames.append(
                        add_metadata(df, excel_file, sheet_name)
                    )
        except Exception:
            logging.exception("Failed reading workbook: %s", excel_file)
            raise

    run_dataframe_pipeline(
        conn=conn,
        frames=frames,
        config=config,
    )
