# OEE ingestion

Loads Excel and MSSQL data into `db/oee.db`.

## Data paths

The only Excel raw-data source is the workspace `data/raw` folder:

```text
data/raw/2026-07-06_start_beam.xlsx
data/raw/textile_days.xlsx
```

The mail downloader writes to this folder. Ingestion does not scan nested
folders such as `data/raw/weaving`.

## Normal ingestion

Run from the workspace root:

```powershell
uv run python oee-ingestion/ingest.py
```

The root `main.py` is only a compatibility wrapper that runs this file.
Normal ingestion loads `textile_days`, `complete_beam`, and `machine_status`.
Start-beam snapshots are ingested one file at a time by Airflow because they
must replay in date order.

Start-beam snapshot helpers live in `oee-ingestion/ingest.py` because they are
job-level entry points, not generic ingestion engine code. The Airflow DAG calls
these helpers for one snapshot partition. Ingestion does not call dbt or build
Gold.

See `oee-orchestration/README.md` for daily and backfill runs.
