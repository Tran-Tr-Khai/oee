from pathlib import Path
import subprocess
from datetime import date

from oee_ingestion.config import ROOT_DIR


PROCESSING_DIR = ROOT_DIR / "oee-processing"


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


def remove_file_if_exists(path: Path) -> bool:
    if not path.exists():
        return False

    path.unlink()
    return True


def get_dag_run_date(dag_run) -> date:
    if dag_run is None:
        raise ValueError("This task requires a DAG run.")

    if getattr(dag_run, "partition_key", None):
        return date.fromisoformat(dag_run.partition_key)

    logical_date = getattr(dag_run, "logical_date", None)
    if logical_date is None:
        raise ValueError("This DAG run has no logical date.")

    return logical_date.in_timezone("Asia/Bangkok").date()
