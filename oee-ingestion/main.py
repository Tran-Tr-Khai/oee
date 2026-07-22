import duckdb

from oee_ingestion.config import (
    DATA_DIR,
    DUCKDB_PATH,
    PipelineConfig,
)
from oee_ingestion.extractors.beam import (
    extract_complete_beam,
    extract_start_beam,
)
from oee_ingestion.extractors.textile_days import (
    extract_textile_days
)
from oee_ingestion.pipeline import run_ingest_pipeline


BEAM_PIPELINES = [
    PipelineConfig(
        table_name="raw_complete_beam",
        file_pattern="*complete_beam*",
        extractor_func=extract_complete_beam,
    ),
    PipelineConfig(
        table_name="raw_start_beam",
        file_pattern="*start_beam*",
        extractor_func=extract_start_beam,
    ),
    PipelineConfig(
        table_name="raw_textile_days",
        file_pattern="*textile_days*",
        extractor_func=extract_textile_days,
    ),
]


def main() -> None:
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(DUCKDB_PATH)) as conn:
        for config in BEAM_PIPELINES:
            run_ingest_pipeline(
                conn=conn,
                data_dir=DATA_DIR,
                config=config,
            )


if __name__ == "__main__":
    main()