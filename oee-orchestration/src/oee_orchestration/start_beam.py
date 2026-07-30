from datetime import date
import logging
from pathlib import Path
import subprocess

import duckdb

from oee_ingestion.config import DUCKDB_PATH, ROOT_DIR
from oee_ingestion.pipeline import table_exists


PROCESSING_DIR = ROOT_DIR / "oee-processing"


def get_partition_date(dag_run) -> date:
    if dag_run is not None and dag_run.partition_key:
        return date.fromisoformat(dag_run.partition_key)

    raise ValueError(
        "This DAG run has no partition date. Use Backfill for a date range, "
        "not Single Run, so Airflow creates partitioned runs."
    )


def prepare_silver(
    snapshot_date: date,
    db_path: Path = DUCKDB_PATH,
) -> str:
    """Prepare Silver for one partition and return its load mode."""
    if not db_path.exists():
        return "baseline"

    with duckdb.connect(str(db_path)) as conn:
        if not table_exists(conn, "slv_start_beam"):
            return "baseline"

        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM slv_start_beam
            WHERE TRY_CAST(source_updated_at AS DATE) < ?
            """,
            [snapshot_date],
        ).fetchone()
        has_baseline = bool(row and row[0])

        if not has_baseline:
            conn.execute("DROP TABLE slv_start_beam")
            logging.info(
                "Reset Silver. %s will be the full baseline.",
                snapshot_date,
            )
            return "baseline"

        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM slv_start_beam
            WHERE TRY_CAST(source_updated_at AS DATE) >= ?
            """,
            [snapshot_date],
        ).fetchone()
        removed_rows = int(row[0]) if row else 0
        conn.execute(
            """
            DELETE FROM slv_start_beam
            WHERE TRY_CAST(source_updated_at AS DATE) >= ?
            """,
            [snapshot_date],
        )
        logging.info(
            "Removed %s Silver rows from %s.",
            f"{removed_rows:,}",
            snapshot_date,
        )
        return "incremental"


def run_dbt(*args: str) -> None:
    subprocess.run(
        [
            "dbt",
            *args,
            "--no-partial-parse",
            "--project-dir",
            str(PROCESSING_DIR),
            "--profiles-dir",
            str(PROCESSING_DIR),
        ],
        cwd=ROOT_DIR,
        check=True,
    )


def build_silver() -> None:
    run_dbt("run", "--select", "slv_start_beam")


def test_silver() -> None:
    run_dbt("test", "--select", "slv_start_beam")


def build_gold() -> None:
    run_dbt(
        "build",
        "--select",
        "slv_start_beam+",
        "--exclude",
        "slv_start_beam",
    )


def remove_snapshot(snapshot_path: Path) -> None:
    snapshot_path.unlink()
    logging.info("Removed source file: %s", snapshot_path)
