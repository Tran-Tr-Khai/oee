# OEE orchestration

Airflow coordinates the OEE layers. The DAG files are:

```text
oee-orchestration/dags/oee_daily_pipeline.py
oee-orchestration/dags/oee_start_beam.py
```

`oee_daily_pipeline` handles normal daily sources:

```text
check_raw_inputs
  -> ingest_raw
  -> build_silver
  -> test_silver
  -> build_gold
  -> cleanup_raw_files
```

It processes `textile_days`, `complete_beam`, `machine_status`, and exactly one
`start_beam` snapshot for the DAG run date.

`oee_start_beam` handles start-beam replay and backfill.

It uses Apache Airflow 3.3 partitioned backfills. One partition is one
`data/raw/YYYY-MM-DD_start_beam.xlsx` file.

## Start-Beam Task Order

```text
locate_snapshot
  -> ingest_raw
  -> prepare_silver
  -> build_silver
  -> test_silver
  -> remove_snapshot
  -> build_gold
```

The Excel file is removed only after the Silver test passes.

The DAG runs from Monday to Saturday at 19:00 in `Asia/Bangkok`. It has
`max_active_runs=1`, so start-beam partitions cannot run at the same time.

## Docker setup

Airflow runs in Linux containers because it does not support native Windows.
Docker Compose uses:

- Airflow 3.3 with `LocalExecutor`.
- PostgreSQL for Airflow metadata.
- One-slot `duckdb_writer` pool.
- `pyproject.toml` and `uv.lock` for all Python dependencies.
- Bind mounts for OEE source code, `data`, `db`, and `logs`.
- The scheduler and task workers call the Airflow Execution API through
  `http://airflow-api-server:8080/execution/`.
- All Airflow components share `AIRFLOW_JWT_SECRET` so Execution API tokens
  signed by the scheduler are accepted by the API server.

Start Docker Desktop first. From the workspace root, copy the local settings:

```powershell
Copy-Item `
  oee-orchestration/.env.example `
  oee-orchestration/.env
```

Build the image from the shared `pyproject.toml` and `uv.lock`:

```powershell
docker build `
  -f oee-orchestration/Dockerfile `
  -t oee-airflow:3.3.0 `
  .
```

Start Airflow without rebuilding:

```powershell
docker compose `
  --env-file oee-orchestration/.env `
  -f oee-orchestration/docker-compose.yml `
  up -d --no-build
```

Open `http://localhost:8080`. The local account is `admin` / `airflow`.
This SimpleAuth account is only for local development.

Check service and DAG status:

```powershell
docker compose `
  --env-file oee-orchestration/.env `
  -f oee-orchestration/docker-compose.yml `
  ps

docker compose `
  --env-file oee-orchestration/.env `
  -f oee-orchestration/docker-compose.yml `
  run --rm airflow-scheduler `
  airflow dags list-import-errors
```

## Check a backfill plan

This command creates no DAG runs:

```powershell
docker compose `
  --env-file oee-orchestration/.env `
  -f oee-orchestration/docker-compose.yml `
  run --rm airflow-scheduler `
  airflow backfill create `
  --dag-id oee_start_beam `
  --from-date 2026-07-06T00:00:00+07:00 `
  --to-date 2026-07-28T23:59:59+07:00 `
  --max-active-runs 1 `
  --reprocess-behavior failed `
  --dry-run
```

Remove `--dry-run` to create the backfill runs. Do not use `--run-backwards`
because start-beam snapshots must run from old to new.

The downloader is not part of this DAG yet. Download all required snapshots
before creating a backfill.

Stop Airflow without deleting PostgreSQL metadata:

```powershell
docker compose `
  --env-file oee-orchestration/.env `
  -f oee-orchestration/docker-compose.yml `
  down
```
