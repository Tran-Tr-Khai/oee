import duckdb

from oee_ingestion.config import (
    DATA_DIR,
    DUCKDB_PATH,
    IncrementalType,
    LoadStrategy,
    PipelineConfig,
    get_mssql_config,
)
from oee_ingestion.sources.beam import (
    extract_complete_beam,
    extract_start_beam,
)
from oee_ingestion.sources.mssql import (
    read_machine_status,
)
from oee_ingestion.sources.textile_days import (
    extract_textile_days
)
from oee_ingestion.pipeline import (
    run_dataframe_pipeline,
    run_ingest_pipeline,
)


EXCEL_PIPELINES = [
    PipelineConfig(
        table_name="raw_complete_beam",
        file_pattern="*complete_beam*",
        extractor_func=extract_complete_beam,
        load_strategy=LoadStrategy.APPEND,
        incremental_column="date",
        incremental_type=IncrementalType.TIMESTAMP,
        sort_columns=("date", "machine", "lot"),
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

        machine_status_df = read_machine_status(mssql_config)
        run_dataframe_pipeline(
            conn=conn,
            frames=[machine_status_df],
            config=MACHINE_STATUS_PIPELINE,
        )


if __name__ == "__main__":
    main()
