# oee-quality

Ad hoc data quality checks for DuckDB tables.

Structure:

- `checks/raw/raw_quality_checks.sql`: raw-layer validation queries
- `checks/silver/silver_quality_checks.sql`: silver-layer validation queries
- `checks/gold/gold_quality_checks.sql`: gold-layer validation queries
- `run_duckdb_checks.py`: executes a `.sql` file statement by statement in read-only mode

Examples:

```powershell
uv run python oee-quality/run_duckdb_checks.py
uv run python oee-quality/run_duckdb_checks.py 0
uv run python oee-quality/run_duckdb_checks.py 1
uv run python oee-quality/run_duckdb_checks.py 2
uv run python oee-quality/run_duckdb_checks.py oee-quality/checks/raw/raw_quality_checks.sql
uv run python oee-quality/run_duckdb_checks.py oee-quality/checks/silver/silver_quality_checks.sql
uv run python oee-quality/run_duckdb_checks.py oee-quality/checks/gold/gold_quality_checks.sql
```

Shortcuts:

- `0`: raw quality checks
- `1`: silver quality checks
- `2`: gold quality checks

If you run from the repo root, the default database path is `db/oee.db`.
