import logging
from pathlib import Path

import pendulum
from airflow.sdk import DAG, task


DUCKDB_POOL = "duckdb_writer"

SILVER_MODELS = [
    "slv_complete_beam",
    "slv_textile_days",
    "slv_machine_status",
    "slv_start_beam",
]


with DAG(
    dag_id="oee_daily_pipeline",
    description="Load normal OEE sources from Raw to Gold.",
    schedule="30 19 * * 1-6",
    start_date=pendulum.datetime(
        2026,
        7,
        6,
        tz="Asia/Bangkok",
    ),
    catchup=False,
    max_active_runs=1,
    tags=["oee", "daily"],
) as dag:

    @task(task_id="check_raw_inputs")
    def check_raw_inputs(dag_run=None) -> dict[str, str | bool]:
        from oee_ingestion.config import DATA_DIR
        from oee_orchestration.pipeline import get_dag_run_date

        run_date = get_dag_run_date(dag_run)
        start_beam_path = DATA_DIR / f"{run_date}_start_beam.xlsx"
        textile_days_exists = (DATA_DIR / "textile_days.xlsx").is_file()
        complete_beam_exists = any(
            path.is_file()
            for path in [
                *DATA_DIR.glob("*complete_beam*.xlsx"),
                *DATA_DIR.glob("*complete_beam*.xls"),
            ]
        )

        if not textile_days_exists:
            raise FileNotFoundError(
                f"Required raw file not found: {DATA_DIR / 'textile_days.xlsx'}"
            )
        if not start_beam_path.is_file():
            raise FileNotFoundError(
                f"Required raw file not found: {start_beam_path}"
            )

        return {
            "date": str(run_date),
            "start_beam_path": str(start_beam_path),
            "textile_days": textile_days_exists,
            "complete_beam": complete_beam_exists,
        }

    @task(
        task_id="ingest_raw",
        retries=2,
        pool=DUCKDB_POOL,
    )
    def ingest_raw(raw_inputs: dict[str, str | bool]) -> dict[str, str | bool]:
        from ingest import (
            ingest_normal_sources,
            ingest_start_beam_snapshot,
        )

        ingest_normal_sources()
        ingest_start_beam_snapshot(Path(str(raw_inputs["start_beam_path"])))
        return raw_inputs

    @task(
        task_id="prepare_start_beam_silver",
        retries=2,
        pool=DUCKDB_POOL,
    )
    def prepare_start_beam_silver(
        raw_inputs: dict[str, str | bool],
    ) -> dict[str, str | bool]:
        from datetime import date

        from oee_orchestration.start_beam import prepare_silver

        mode = prepare_silver(date.fromisoformat(str(raw_inputs["date"])))
        return {**raw_inputs, "start_beam_mode": mode}

    @task(
        task_id="build_silver",
        retries=2,
        pool=DUCKDB_POOL,
    )
    def build_silver(raw_inputs: dict[str, str | bool]) -> dict[str, str | bool]:
        from oee_orchestration.pipeline import run_dbt

        run_dbt("run", "--select", *SILVER_MODELS)
        return raw_inputs

    @task(
        task_id="test_silver",
        retries=1,
        pool=DUCKDB_POOL,
    )
    def test_silver(raw_inputs: dict[str, str | bool]) -> dict[str, str | bool]:
        from oee_orchestration.pipeline import run_dbt

        run_dbt("test", "--select", *SILVER_MODELS)
        return raw_inputs

    @task(
        task_id="build_gold",
        retries=2,
        pool=DUCKDB_POOL,
    )
    def build_gold(raw_inputs: dict[str, str | bool]) -> dict[str, str | bool]:
        from oee_orchestration.pipeline import run_dbt

        run_dbt(
            "build",
            "--select",
            *(f"{model}+" for model in SILVER_MODELS),
            "--exclude",
            *SILVER_MODELS,
        )
        return raw_inputs

    @task(task_id="cleanup_raw_files")
    def cleanup_raw_files(raw_inputs: dict[str, str | bool]) -> None:
        from oee_ingestion.config import DATA_DIR
        from oee_orchestration.pipeline import remove_file_if_exists

        raw_files = [
            DATA_DIR / "textile_days.xlsx",
            Path(str(raw_inputs["start_beam_path"])),
        ]
        raw_files.extend(
            [
                *DATA_DIR.glob("*complete_beam*.xlsx"),
                *DATA_DIR.glob("*complete_beam*.xls"),
            ]
        )

        for raw_file in raw_files:
            if remove_file_if_exists(Path(raw_file)):
                logging.info("Removed processed raw file: %s", raw_file)

    raw_inputs = check_raw_inputs()
    ingested = ingest_raw(raw_inputs)
    prepared = prepare_start_beam_silver(ingested)
    silver = build_silver(prepared)
    tested = test_silver(silver)
    gold = build_gold(tested)
    cleanup_raw_files(gold)
