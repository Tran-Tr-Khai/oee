from datetime import date
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import duckdb

from oee_orchestration.pipeline import get_dag_run_date, remove_file_if_exists
from oee_orchestration.start_beam import (
    get_partition_date,
    prepare_silver,
)

INGESTION_MAIN = (
    Path(__file__).resolve().parents[2] / "oee-ingestion" / "ingest.py"
)
spec = importlib.util.spec_from_file_location(
    "oee_ingestion_entrypoint",
    INGESTION_MAIN,
)
if spec is None or spec.loader is None:
    raise ImportError(f"Cannot load ingestion main: {INGESTION_MAIN}")
ingestion_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingestion_main)
find_start_beam_snapshot = ingestion_main.find_start_beam_snapshot


class FakeDagRun:
    def __init__(
        self,
        partition_key: str | None,
        logical_date=None,
    ) -> None:
        self.partition_key = partition_key
        self.logical_date = logical_date


class PartitionDateTests(unittest.TestCase):
    def test_gets_partition_date_from_partition_key(self) -> None:
        result = get_partition_date(FakeDagRun("2026-07-06"))

        self.assertEqual(result, date(2026, 7, 6))

    def test_rejects_non_partitioned_manual_run(self) -> None:
        with self.assertRaisesRegex(ValueError, "Use Backfill"):
            get_partition_date(FakeDagRun(None))

    def test_gets_daily_date_from_logical_date(self) -> None:
        import pendulum

        result = get_dag_run_date(
            FakeDagRun(
                None,
                pendulum.datetime(2026, 7, 29, 12, 30, tz="UTC"),
            )
        )

        self.assertEqual(result, date(2026, 7, 29))


class FindSnapshotTests(unittest.TestCase):
    def test_finds_snapshot_in_raw_folder(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            expected_path = data_dir / "2026-07-06_start_beam.xlsx"
            expected_path.touch()

            result = find_start_beam_snapshot(
                snapshot_date=date(2026, 7, 6),
                data_dir=data_dir,
            )

            self.assertEqual(result, expected_path)

    def test_rejects_duplicate_snapshots(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "2026-07-06_start_beam.xlsx").touch()
            (data_dir / "2026-07-06_start_beam.xls").touch()

            with self.assertRaises(ValueError):
                find_start_beam_snapshot(
                    snapshot_date=date(2026, 7, 6),
                    data_dir=data_dir,
                )


class PrepareSilverTests(unittest.TestCase):
    def test_drops_silver_when_no_older_baseline_exists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "oee.db"
            with duckdb.connect(str(db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE slv_start_beam AS
                    SELECT DATE '2026-07-17' AS source_updated_at
                    """
                )

            mode = prepare_silver(
                snapshot_date=date(2026, 7, 6),
                db_path=db_path,
            )

            with duckdb.connect(str(db_path)) as conn:
                table_count = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_name = 'slv_start_beam'
                    """
                ).fetchone()[0]

            self.assertEqual(mode, "baseline")
            self.assertEqual(table_count, 0)

    def test_keeps_older_rows_and_removes_rows_from_partition(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "oee.db"
            with duckdb.connect(str(db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE slv_start_beam AS
                    SELECT * FROM (
                        VALUES
                            (DATE '2026-07-09'),
                            (DATE '2026-07-10'),
                            (DATE '2026-07-11')
                    ) AS source(source_updated_at)
                    """
                )

            mode = prepare_silver(
                snapshot_date=date(2026, 7, 10),
                db_path=db_path,
            )

            with duckdb.connect(str(db_path)) as conn:
                dates = conn.execute(
                    """
                    SELECT source_updated_at
                    FROM slv_start_beam
                    ORDER BY source_updated_at
                    """
                ).fetchall()

            self.assertEqual(mode, "incremental")
            self.assertEqual(dates, [(date(2026, 7, 9),)])


class CleanupTests(unittest.TestCase):
    def test_remove_file_if_exists_returns_false_for_missing_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.xlsx"

            self.assertFalse(remove_file_if_exists(missing_path))

    def test_remove_file_if_exists_removes_existing_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            existing_path = Path(temp_dir) / "textile_days.xlsx"
            existing_path.touch()

            self.assertTrue(remove_file_if_exists(existing_path))
            self.assertFalse(existing_path.exists())


if __name__ == "__main__":
    unittest.main()
