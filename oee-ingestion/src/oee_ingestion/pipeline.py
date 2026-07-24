from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path

import duckdb
import pandas as pd

from oee_ingestion.config import (
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


def get_table_row_count(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> int:
    return conn.execute(
        f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
    ).fetchone()[0]


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


def get_merge_keys(
    config: PipelineConfig,
    target_columns: list[str],
) -> list[str]:
    if config.merge_keys:
        return list(config.merge_keys)

    return [
        column
        for column in target_columns
        if not column.startswith("_")
    ]


def build_merge_condition(merge_keys: list[str]) -> str:
    return " AND ".join(
        f"target.{quote_identifier(key)} "
        f"IS NOT DISTINCT FROM source.{quote_identifier(key)}"
        for key in merge_keys
    )


def deduplicate_upsert_frame(
    df: pd.DataFrame,
    merge_keys: list[str],
) -> pd.DataFrame:
    if not merge_keys:
        return df.reset_index(drop=True)

    return (
        df.drop_duplicates(
            subset=merge_keys,
            keep="last",
        )
        .reset_index(drop=True)
    )


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


def upsert_table(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    frames: list[pd.DataFrame],
    target_columns: list[str],
    merge_keys: list[str],
) -> int:
    source_df = deduplicate_upsert_frame(
        df=pd.concat(frames, ignore_index=True),
        merge_keys=merge_keys,
    )
    source_columns = list(source_df.columns)
    quoted_table = quote_identifier(table_name)

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
    source_columns = list(source_df.columns)

    merge_columns = [
        key
        for key in (
            resolved_columns.get(key, key)
            for key in merge_keys
        )
        if key in target_columns and key in source_columns
    ]
    if not merge_columns:
        raise ValueError(
            f"No valid merge keys configured for {table_name}"
        )

    aligned_df = source_df.reindex(columns=target_columns).astype("string")
    update_columns = [
        column
        for column in source_columns
        if column not in merge_columns
    ]
    merge_condition = build_merge_condition(merge_columns)
    update_assignments = ", ".join(
        f"{quote_identifier(column)} = source.{quote_identifier(column)}"
        for column in update_columns
    )
    insert_columns = ", ".join(
        quote_identifier(column)
        for column in target_columns
    )
    insert_values = ", ".join(
        f"source.{quote_identifier(column)}"
        for column in target_columns
    )

    with registered_frame(conn, aligned_df) as relation_name:
        merge_sql = (
            f"MERGE INTO {quoted_table} AS target "
            f"USING {quote_identifier(relation_name)} AS source "
            f"ON {merge_condition} "
        )
        if update_assignments:
            merge_sql += f"WHEN MATCHED THEN UPDATE SET {update_assignments} "
        merge_sql += (
            f"WHEN NOT MATCHED THEN INSERT ({insert_columns}) "
            f"VALUES ({insert_values})"
        )
        conn.execute(merge_sql)

    return len(aligned_df)


def run_ingest_pipeline(
    conn: duckdb.DuckDBPyConnection,
    data_dir: Path,
    config: PipelineConfig,
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

    target_columns = list(union_schema)
    merge_keys = get_merge_keys(config, target_columns)
    try:
        if config.load_strategy == LoadStrategy.UPSERT:
            total_rows = upsert_table(
                conn=conn,
                table_name=config.table_name,
                frames=frames,
                target_columns=target_columns,
                merge_keys=merge_keys,
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
