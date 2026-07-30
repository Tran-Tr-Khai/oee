from datetime import date
from pathlib import Path

import pendulum
from airflow.sdk import CronPartitionTimetable, DAG, task
from oee_orchestration.start_beam import get_partition_date


DUCKDB_POOL = "duckdb_writer"


with DAG(
    dag_id="oee_start_beam",
    description="Load one start-beam snapshot from Raw to Gold.",
    schedule=CronPartitionTimetable(
        "0 19 * * 1-6",
        timezone="Asia/Bangkok",
        key_format="%Y-%m-%d",
    ),
    start_date=pendulum.datetime(
        2026,
        7,
        6,
        tz="Asia/Bangkok",
    ),
    catchup=False,
    max_active_runs=1,
    tags=["oee", "weaving", "start-beam"],
) as dag:

    @task(
        task_id="locate_snapshot",
        retries=2,
        depends_on_past=True,
    )
    def locate_snapshot(dag_run=None) -> dict[str, str]:
        snapshot_date = get_partition_date(dag_run)

        from ingest import find_start_beam_snapshot

        snapshot_path = find_start_beam_snapshot(snapshot_date)
        return {
            "date": str(snapshot_date),
            "path": str(snapshot_path),
        }

    @task(
        task_id="ingest_raw",
        retries=2,
        pool=DUCKDB_POOL,
    )
    def ingest_raw(snapshot: dict[str, str]) -> dict[str, str]:
        from ingest import ingest_start_beam_snapshot

        ingest_start_beam_snapshot(Path(snapshot["path"]))
        return snapshot

    @task(
        task_id="prepare_silver",
        retries=2,
        pool=DUCKDB_POOL,
    )
    def prepare_silver(snapshot: dict[str, str]) -> dict[str, str]:
        from oee_orchestration.start_beam import (
            prepare_silver as prepare_silver_partition,
        )

        mode = prepare_silver_partition(
            date.fromisoformat(snapshot["date"])
        )
        return {**snapshot, "mode": mode}

    @task(
        task_id="build_silver",
        retries=2,
        pool=DUCKDB_POOL,
    )
    def build_silver(snapshot: dict[str, str]) -> dict[str, str]:
        from oee_orchestration.start_beam import (
            build_silver as build_silver_model,
        )

        build_silver_model()
        return snapshot

    @task(
        task_id="test_silver",
        retries=1,
        pool=DUCKDB_POOL,
    )
    def test_silver(snapshot: dict[str, str]) -> dict[str, str]:
        from oee_orchestration.start_beam import (
            test_silver as test_silver_model,
        )

        test_silver_model()
        return snapshot

    @task(
        task_id="remove_snapshot",
        retries=2,
    )
    def remove_snapshot(snapshot: dict[str, str]) -> str:
        from oee_orchestration.start_beam import (
            remove_snapshot as remove_snapshot_file,
        )

        snapshot_path = Path(snapshot["path"])
        remove_snapshot_file(snapshot_path)
        return str(snapshot_path)

    @task(
        task_id="build_gold",
        retries=2,
        pool=DUCKDB_POOL,
    )
    def build_gold(_removed_snapshot: str) -> None:
        from oee_orchestration.start_beam import (
            build_gold as build_gold_models,
        )

        build_gold_models()

    snapshot = locate_snapshot()
    raw_snapshot = ingest_raw(snapshot)
    prepared_snapshot = prepare_silver(raw_snapshot)
    silver_snapshot = build_silver(prepared_snapshot)
    tested_snapshot = test_silver(silver_snapshot)
    removed_snapshot = remove_snapshot(tested_snapshot)
    build_gold(removed_snapshot)
