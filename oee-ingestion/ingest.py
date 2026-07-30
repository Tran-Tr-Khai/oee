from datetime import date
from pathlib import Path

import duckdb

from oee_ingestion.config import (
    DATA_DIR,
    DUCKDB_PATH,
    IncrementalType,
    LoadStrategy,
    PipelineConfig,
    get_mssql_config,
)
from oee_ingestion.pipeline import (
    get_latest_incremental_value,
    run_dataframe_pipeline,
    run_ingest_files,
    run_ingest_pipeline,
    table_exists,
)
from oee_ingestion.sources.beam import (
    extract_complete_beam,
    extract_start_beam,
)
from oee_ingestion.sources.mssql import (
    read_machine_status,
)
from oee_ingestion.sources.textile_days import (
    extract_textile_days,
)


EXCEL_PIPELINES = [
    PipelineConfig(
        table_name="raw_complete_beam",
        file_pattern="*complete_beam*",
        extractor_func=extract_complete_beam,
        load_strategy=LoadStrategy.APPEND,
        incremental_column="date",
        incremental_type=IncrementalType.TIMESTAMP,
        sort_columns=("date", "machine", "lot", "shift", "worker"),
    ),
    PipelineConfig(
        table_name="raw_start_beam",
        file_pattern="*start_beam*",
        extractor_func=extract_start_beam,
        load_strategy=LoadStrategy.REPLACE,
    ),
    PipelineConfig(
        table_name="raw_textile_days",
        file_pattern="*textile_days*",
        extractor_func=extract_textile_days,
        load_strategy=LoadStrategy.APPEND,
        incremental_column="prod_date",
        incremental_type=IncrementalType.TIMESTAMP,
        sort_columns=("prod_date", "machine_no"),
    ),
]

MACHINE_STATUS_PIPELINE = PipelineConfig(
    table_name="raw_machine_status",
    load_strategy=LoadStrategy.APPEND,
    incremental_column="id",
    incremental_type=IncrementalType.BIGINT,
    sort_columns=("id",),
)

START_BEAM_CONFIG = next(
    config
    for config in EXCEL_PIPELINES
    if config.table_name == "raw_start_beam"
)


def find_start_beam_snapshot(
    snapshot_date: date,
    data_dir: Path = DATA_DIR,
) -> Path:
    expected_stem = f"{snapshot_date}_start_beam"
    matches = sorted(
        path
        for path in data_dir.glob(f"{expected_stem}.*")
        if path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.casefold() in {".xlsx", ".xls"}
    )

    if not matches:
        raise FileNotFoundError(
            f"Snapshot not found: {expected_stem}.xlsx"
        )
    if len(matches) > 1:
        raise ValueError(
            f"More than one start-beam snapshot found for {snapshot_date}: "
            + ", ".join(str(path) for path in matches)
        )
    return matches[0]


def ingest_start_beam_snapshot(
    snapshot_path: Path,
    db_path: Path = DUCKDB_PATH,
) -> None:
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path)) as conn:
        run_ingest_files(
            conn=conn,
            excel_files=[snapshot_path],
            config=START_BEAM_CONFIG,
        )


def main() -> None:
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    mssql_config = get_mssql_config()

    with duckdb.connect(str(DUCKDB_PATH)) as conn:
        for config in EXCEL_PIPELINES:
            run_ingest_pipeline(
                conn=conn,
                data_dir=DATA_DIR,
                config=config,
            )

        latest_machine_status_id = None
        if table_exists(conn, MACHINE_STATUS_PIPELINE.table_name):
            latest_machine_status_id = get_latest_incremental_value(
                conn=conn,
                table_name=MACHINE_STATUS_PIPELINE.table_name,
                incremental_column=MACHINE_STATUS_PIPELINE.incremental_column,
                incremental_type=MACHINE_STATUS_PIPELINE.incremental_type,
            )

        machine_status_df = read_machine_status(
            mssql_config,
            min_id=latest_machine_status_id,
        )
        run_dataframe_pipeline(
            conn=conn,
            frames=[machine_status_df],
            config=MACHINE_STATUS_PIPELINE,
        )


if __name__ == "__main__":
    main()
